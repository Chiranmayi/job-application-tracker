
from datetime import datetime
from typing import Literal, Self

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    HttpUrl,
    model_validator,
)


ApplicationStatus = Literal[
    "SAVED",
    "APPLIED",
    "SCREENING",
    "INTERVIEW",
    "OFFER",
    "ACCEPTED",
    "REJECTED",
    "WITHDRAWN",
]


class UserRegister(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr

    model_config = {"from_attributes": True}


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class JobApplicationCreate(BaseModel):
    company_name: str = Field(min_length=1, max_length=150)
    job_title: str = Field(min_length=1, max_length=150)
    location: str | None = Field(default=None, max_length=150)
    employment_type: str | None = Field(default=None, max_length=50)
    source: str | None = Field(default=None, max_length=100)
    job_url: HttpUrl | None = None

    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    applied_at: datetime | None = None

    status: ApplicationStatus = "APPLIED"

    @model_validator(mode="after")
    def validate_application(self) -> Self:
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError(
                "Minimum salary cannot exceed maximum salary"
            )

        if self.company_name.strip() == "":
            raise ValueError("Company name cannot be blank")

        if self.job_title.strip() == "":
            raise ValueError("Job title cannot be blank")

        return self


class InterviewCreate(BaseModel):
    interview_date: datetime
    interview_type: str = Field(min_length=1, max_length=50)
    location: str | None = Field(default=None, max_length=255)
    meeting_link: HttpUrl | None = None
    interviewer_name: str | None = Field(default=None, max_length=150)
    feedback: str | None = None
    status: Literal[
        "SCHEDULED",
        "COMPLETED",
        "CANCELLED",
    ] = "SCHEDULED"


class InterviewResponse(InterviewCreate):
    id: int
    application_id: int
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class NoteCreate(BaseModel):
    content: str = Field(min_length=1)


class NoteResponse(BaseModel):
    id: int
    application_id: int
    content: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class FollowUpCreate(BaseModel):
    follow_up_date: datetime
    follow_up_type: str = Field(min_length=1, max_length=50)
    notes: str | None = None
    completed: bool = False


class FollowUpUpdate(BaseModel):
    follow_up_date: datetime | None = None
    follow_up_type: str | None = Field(default=None, max_length=50)
    notes: str | None = None
    completed: bool | None = None


class FollowUpResponse(FollowUpCreate):
    id: int
    application_id: int
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
