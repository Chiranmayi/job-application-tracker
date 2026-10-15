from datetime import date, datetime, time, timedelta
from math import ceil
from typing import Literal

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, JobApplication, Interview, Note, FollowUp
from app.schemas import (
    UserRegister,
    UserResponse,
    UserLogin,
    JobApplicationCreate,
    InterviewCreate,
    NoteCreate,
    FollowUpCreate,
    FollowUpUpdate,
)
from app.security import (
    hash_password,
    verify_password,
    create_access_token,
    verify_access_token,
)


app = FastAPI(
    title="Job Application Tracker API",
    description="API for managing job applications, interviews, notes and follow-ups.",
    version="2.0.0",
)

security = HTTPBearer(auto_error=False)

ApplicationStatus = Literal[
    "SAVED", "APPLIED", "SCREENING", "INTERVIEW",
    "OFFER", "ACCEPTED", "REJECTED", "WITHDRAWN",
]

ALLOWED_TRANSITIONS = {
    "SAVED": {"APPLIED", "WITHDRAWN"},
    "APPLIED": {"SCREENING", "INTERVIEW", "REJECTED", "WITHDRAWN"},
    "SCREENING": {"INTERVIEW", "OFFER", "REJECTED", "WITHDRAWN"},
    "INTERVIEW": {"SCREENING", "OFFER", "REJECTED", "WITHDRAWN"},
    "OFFER": {"ACCEPTED", "REJECTED", "WITHDRAWN"},
    "ACCEPTED": set(),
    "REJECTED": set(),
    "WITHDRAWN": set(),
}


# -------------------- HOME --------------------

@app.get("/")
def home():
    return {"message": "Job Application Tracker API is running"}


# -------------------- AUTHENTICATION --------------------

@app.post("/auth/register", response_model=UserResponse, status_code=201)
@app.post("/register", response_model=UserResponse, status_code=201, include_in_schema=False)
def register_user(
    user_data: UserRegister,
    db: Session = Depends(get_db),
):
    email = str(user_data.email).lower()

    existing = db.query(User).filter(
        func.lower(User.email) == email
    ).first()

    if existing:
        raise HTTPException(409, "Email is already registered")

    user = User(
        name=user_data.name.strip(),
        email=email,
        password=hash_password(user_data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/login")
def login_user(
    login_data: UserLogin,
    db: Session = Depends(get_db),
):
    email = str(login_data.email).lower()
    user = db.query(User).filter(
        func.lower(User.email) == email
    ).first()

    if not user or not verify_password(login_data.password, user.password):
        raise HTTPException(401, "Invalid email or password")

    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
    }


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
):
    if credentials is None:
        raise HTTPException(
            401,
            "Authentication token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = verify_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(401, "Invalid or expired token")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(401, "User not found")

    return user


# -------------------- HELPERS --------------------

def get_owned_application(application_id: int, user_id: int, db: Session):
    application = db.query(JobApplication).filter(
        JobApplication.id == application_id,
        JobApplication.user_id == user_id,
    ).first()

    if application is None:
        raise HTTPException(404, "Application not found")

    return application


def get_owned_related(model, record_id: int, user_id: int, db: Session):
    """Fetch an interview, note or follow-up through its owned application."""
    record = db.query(model).filter(model.id == record_id).first()

    if record is None:
        raise HTTPException(404, "Record not found")

    get_owned_application(record.application_id, user_id, db)
    return record


def validate_applied_date(value: datetime | None):
    if value is not None and value.date() > date.today():
        raise HTTPException(422, "Applied date cannot be in the future")


def validate_future_followup(value: datetime):
    if value.date() < date.today():
        raise HTTPException(422, "Follow-up date cannot be in the past")


# -------------------- APPLICATIONS --------------------

@app.post("/applications", status_code=201)
def create_application(
    data: JobApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    validate_applied_date(data.applied_at)

    application = JobApplication(
        company_name=data.company_name.strip(),
        job_title=data.job_title.strip(),
        location=data.location,
        employment_type=data.employment_type,
        source=data.source,
        job_url=str(data.job_url) if data.job_url else None,
        salary_min=data.salary_min,
        salary_max=data.salary_max,
        status=data.status,
        user_id=current_user.id,
    )

    if data.applied_at is not None:
        application.applied_at = data.applied_at

    db.add(application)
    db.commit()
    db.refresh(application)
    return application


@app.get("/applications")
def list_applications(
    search: str | None = None,
    company: str | None = None,
    job_title: str | None = None,
    # Support both ?status_filter=INTERVIEW (existing tests/clients)
    # and ?status=INTERVIEW (shorter public query parameter).
    status_filter: ApplicationStatus | None = Query(default=None),
    status: ApplicationStatus | None = Query(default=None),
    location: str | None = None,
    source: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    sort_by: Literal[
        "id", "company_name", "job_title", "status",
        "applied_at", "created_at", "updated_at",
        "salary_min", "salary_max",
    ] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    skip: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(422, "from_date cannot be after to_date")

    query = db.query(JobApplication).filter(
        JobApplication.user_id == current_user.id
    )

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(
            JobApplication.company_name.ilike(term),
            JobApplication.job_title.ilike(term),
        ))

    if company:
        query = query.filter(
            JobApplication.company_name.ilike(f"%{company.strip()}%")
        )

    if job_title:
        query = query.filter(
            JobApplication.job_title.ilike(f"%{job_title.strip()}%")
        )

    selected_status = status if status is not None else status_filter
    if selected_status:
        query = query.filter(JobApplication.status == selected_status)

    if location:
        query = query.filter(
            JobApplication.location.ilike(f"%{location.strip()}%")
        )

    if source:
        query = query.filter(
            JobApplication.source.ilike(f"%{source.strip()}%")
        )

    if from_date:
        query = query.filter(
            JobApplication.applied_at >= datetime.combine(from_date, time.min)
        )

    if to_date:
        query = query.filter(
            JobApplication.applied_at < datetime.combine(
                to_date + timedelta(days=1), time.min
            )
        )

    total = query.count()
    column = getattr(JobApplication, sort_by)
    ordering = column.asc() if sort_order == "asc" else column.desc()
    query = query.order_by(ordering)

    offset = skip if skip is not None else (page - 1) * limit
    records = query.offset(offset).limit(limit).all()

    return {
        "page": offset // limit + 1,
        "limit": limit,
        "total": total,
        "total_pages": ceil(total / limit) if total else 0,
        "data": records,
    }


@app.get("/applications/{application_id}")
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_owned_application(application_id, current_user.id, db)


@app.put("/applications/{application_id}")
def edit_application(
    application_id: int,
    data: JobApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    application = get_owned_application(application_id, current_user.id, db)
    validate_applied_date(data.applied_at)

    for field in (
        "company_name", "job_title", "location",
        "employment_type", "source", "salary_min",
        "salary_max", "status",
    ):
        value = getattr(data, field)
        if field in ("company_name", "job_title"):
            value = value.strip()
        setattr(application, field, value)

    application.job_url = str(data.job_url) if data.job_url else None
    if data.applied_at is not None:
        application.applied_at = data.applied_at

    db.commit()
    db.refresh(application)
    return application


@app.patch("/applications/{application_id}/status")
def change_application_status(
    application_id: int,
    new_status: ApplicationStatus,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    application = get_owned_application(application_id, current_user.id, db)

    if application.status != new_status:
        allowed = ALLOWED_TRANSITIONS.get(application.status, set())
        if new_status not in allowed:
            raise HTTPException(
                422,
                f"Status cannot change from {application.status} to {new_status}",
            )

        application.status = new_status
        db.commit()
        db.refresh(application)

    return application


@app.delete("/applications/{application_id}")
def delete_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    application = get_owned_application(application_id, current_user.id, db)
    db.delete(application)
    db.commit()
    return {"message": "Application deleted successfully"}


# -------------------- INTERVIEWS --------------------

@app.post("/applications/{application_id}/interviews", status_code=201)
def create_interview(
    application_id: int,
    data: InterviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_application(application_id, current_user.id, db)

    interview = Interview(
        application_id=application_id,
        interview_date=data.interview_date,
        interview_type=data.interview_type,
        location=data.location,
        meeting_link=str(data.meeting_link) if data.meeting_link else None,
        interviewer_name=data.interviewer_name,
        feedback=data.feedback,
        status=data.status,
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return interview


@app.get("/applications/{application_id}/interviews")
def list_interviews(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_application(application_id, current_user.id, db)
    return db.query(Interview).filter(
        Interview.application_id == application_id
    ).order_by(Interview.interview_date.asc()).all()


@app.put("/interviews/{interview_id}")
def edit_interview(
    interview_id: int,
    data: InterviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    interview = get_owned_related(
        Interview, interview_id, current_user.id, db
    )

    interview.interview_date = data.interview_date
    interview.interview_type = data.interview_type
    interview.location = data.location
    interview.meeting_link = str(data.meeting_link) if data.meeting_link else None
    interview.interviewer_name = data.interviewer_name
    interview.feedback = data.feedback
    interview.status = data.status

    db.commit()
    db.refresh(interview)
    return interview


@app.delete("/interviews/{interview_id}")
def delete_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    interview = get_owned_related(
        Interview, interview_id, current_user.id, db
    )
    db.delete(interview)
    db.commit()
    return {"message": "Interview deleted successfully"}


# -------------------- NOTES --------------------

@app.post("/applications/{application_id}/notes", status_code=201)
def create_note(
    application_id: int,
    data: NoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_application(application_id, current_user.id, db)

    note = Note(
        application_id=application_id,
        content=data.content.strip(),
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@app.get("/applications/{application_id}/notes")
def list_notes(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_application(application_id, current_user.id, db)
    return db.query(Note).filter(
        Note.application_id == application_id
    ).order_by(Note.created_at.desc()).all()


@app.put("/notes/{note_id}")
def edit_note(
    note_id: int,
    data: NoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note = get_owned_related(Note, note_id, current_user.id, db)
    note.content = data.content.strip()
    db.commit()
    db.refresh(note)
    return note


@app.delete("/notes/{note_id}")
def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note = get_owned_related(Note, note_id, current_user.id, db)
    db.delete(note)
    db.commit()
    return {"message": "Note deleted successfully"}


# -------------------- FOLLOW-UPS --------------------

@app.post("/applications/{application_id}/followups", status_code=201)
def create_followup(
    application_id: int,
    data: FollowUpCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_application(application_id, current_user.id, db)
    validate_future_followup(data.follow_up_date)

    followup = FollowUp(
        application_id=application_id,
        follow_up_date=data.follow_up_date,
        follow_up_type=data.follow_up_type,
        notes=data.notes,
        completed=data.completed,
    )
    db.add(followup)
    db.commit()
    db.refresh(followup)
    return followup


@app.get("/applications/{application_id}/followups")
def list_followups(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_application(application_id, current_user.id, db)
    return db.query(FollowUp).filter(
        FollowUp.application_id == application_id
    ).order_by(FollowUp.follow_up_date.asc()).all()


@app.patch("/followups/{followup_id}")
def edit_followup(
    followup_id: int,
    data: FollowUpUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    followup = get_owned_related(
        FollowUp, followup_id, current_user.id, db
    )

    updates = data.model_dump(exclude_unset=True)
    if "follow_up_date" in updates and updates["follow_up_date"] is not None:
        validate_future_followup(updates["follow_up_date"])

    for field, value in updates.items():
        setattr(followup, field, value)

    db.commit()
    db.refresh(followup)
    return followup


@app.delete("/followups/{followup_id}")
def delete_followup(
    followup_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    followup = get_owned_related(
        FollowUp, followup_id, current_user.id, db
    )
    db.delete(followup)
    db.commit()
    return {"message": "Follow-up deleted successfully"}


@app.get("/followups/upcoming")
def upcoming_followups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(FollowUp)
        .join(
            JobApplication,
            FollowUp.application_id == JobApplication.id,
        )
        .filter(
            JobApplication.user_id == current_user.id,
            FollowUp.completed.is_(False),
            FollowUp.follow_up_date >= datetime.now(),
        )
        .order_by(FollowUp.follow_up_date.asc())
        .all()
    )


# -------------------- DASHBOARD --------------------

@app.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(JobApplication).filter(
        JobApplication.user_id == current_user.id
    )
    total = query.count()

    status_rows = (
        db.query(JobApplication.status, func.count(JobApplication.id))
        .filter(JobApplication.user_id == current_user.id)
        .group_by(JobApplication.status)
        .all()
    )
    status_counts = {name: count for name, count in status_rows}

    interview_count = status_counts.get("INTERVIEW", 0)
    offer_count = status_counts.get("OFFER", 0)
    accepted_count = status_counts.get("ACCEPTED", 0)
    rejected_count = status_counts.get("REJECTED", 0)

    return {
        "total_applications": total,
        "status_counts": status_counts,
        "interview_rate": round(interview_count / total * 100, 2) if total else 0,
        "offer_rate": round((offer_count + accepted_count) / total * 100, 2) if total else 0,
        "rejection_rate": round(rejected_count / total * 100, 2) if total else 0,
    }


@app.get("/dashboard/companies")
def company_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(
            JobApplication.company_name,
            func.count(JobApplication.id).label("application_count"),
        )
        .filter(JobApplication.user_id == current_user.id)
        .group_by(JobApplication.company_name)
        .order_by(func.count(JobApplication.id).desc())
        .all()
    )

    return {
        "companies": [
            {"company_name": name, "application_count": count}
            for name, count in rows
        ]
    }
