# ExamGuard AI

ExamGuard AI is a starter project for secure online exams. It includes a FastAPI backend, static frontend pages, webcam verification hooks, lockdown logging, IP/geofence checks, CSV upload, PIN generation, and Excel report export.

## Project Structure

```text
backend/
  app/
    api/
    core/
    db/
    services/
    schemas/
    main.py
    config.py
  requirements.txt
  .env
frontend/
  public/
  src/
reports/
README.md
.gitignore
```

## Backend Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend URL:

```text
http://127.0.0.1:8000
```

API docs:

```text
http://127.0.0.1:8000/docs
```

## Frontend

Open this file in a browser:

```text
frontend/public/index.html
```

Or open the pages directly:

```text
frontend/src/pages/login.html
frontend/src/pages/exam.html
frontend/src/pages/admin.html
```

## Default Admin

```text
Username: admin
Password: admin123
```

Change these values in `backend/.env` before using the project seriously.

## Email Invites

Admins can upload a `.csv`, `.xlsx`, `.xlsm`, or `.xls` sheet with `name` and `email` columns from the admin panel. The backend stores or updates students, generates one-time exam invitation links, and sends them through the configured SMTP service.

Set these values in `backend/.env` for real email delivery:

```text
SMTP_HOST=
SMTP_PORT=
SMTP_USER=
SMTP_PASSWORD=
EMAIL_FROM=
FRONTEND_EXAM_URL=http://127.0.0.1:8000/frontend/src/pages/exam.html
EXAM_INVITE_EXPIRE_HOURS=72
```
