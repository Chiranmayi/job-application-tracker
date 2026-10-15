# Job Application Tracker

## 1. Project Overview

The Job Application Tracker is a REST API built with FastAPI and PostgreSQL that helps users manage job applications and track their job-search progress.

Users can register, log in, maintain application records, manage interviews, add notes and follow-ups, and view application statistics.

## 2. Features

- User registration and login
- Password hashing and JWT-based authentication
- Create, view, update, and delete job applications
- Application status management
- Search, filtering, sorting, and pagination
- Interview management
- Notes and follow-up management
- Dashboard statistics
- User-specific access control
- Request validation and error handling
- Automated tests using pytest

## 3. Tech Stack

- Language:Python
- API framework: FastAPI
- Database: PostgreSQL
- ORM: SQLAlchemy
- Validation:Pydantic
- Authentication: JWT
- Password hashing: pwdlib
- Testing: pytest and FastAPI TestClient
- Dependency management: uv

## 4. Project Structure

text
Project2/
├── app/
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   └── security.py
├── tests/
│   └── test_main.py
├── main.py
├── test_db.py
├── requirements.txt
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
└── README.md


## 5. Database Schema

The project uses PostgreSQL and SQLAlchemy.

- users: stores user information and hashed passwords.
- job_applications: stores job details, salary range, application status, and ownership.
- interviews: stores interview information linked to applications.
- notes: stores notes linked to applications.
- followups: stores follow-up dates, notes, and completion status.

Applications belong to users. Interviews, notes, and follow-ups are associated with their respective applications.

## 6. Running the Project

### Prerequisites

- Python 3.12 or compatible version
- PostgreSQL
- uv

### Setup

1. Clone or download the repository.
2. Create a PostgreSQL database named `job_tracker`.
3. Copy `.env.example` to `.env`.
4. Update `.env` with your PostgreSQL credentials and a private JWT secret.
5. Install dependencies:

 powershell
uv sync
  

6. Start the API:

   powershell
   uv run uvicorn main:app --reload
   

7. Open the interactive API documentation:

   `http://127.0.0.1:8000/docs`

## 7. Environment Variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection URL |
| `SECRET_KEY` | Secret used to sign JWTs |
| `ALGORITHM` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime in minutes |

Never upload your real `.env` file, database password, or JWT secret to GitHub.

## 8. API Endpoints

The API includes endpoints for:

- Authentication and user registration
- Job application CRUD operations
- Application search, filters, sorting, and pagination
- Application status updates
- Interviews
- Notes
- Follow-ups
- Dashboard statistics and company statistics

Open `/docs` while the server is running for the exact endpoint paths, request schemas, and response formats.

## 9. Testing

The project includes automated tests using pytest and FastAPI TestClient.

Run the test suite:

powershell
uv run pytest -v


The test suite previously completed with **44 passing tests**.

## 10. Screenshots

Added screenshots of the running API and important operations to a `screenshots/` folder before submission.

## 11. Future Enhancements

- Build a dedicated web frontend.
- Add reminders for interviews and follow-ups.
- Add application activity history.
- Improve dashboard visualizations.
