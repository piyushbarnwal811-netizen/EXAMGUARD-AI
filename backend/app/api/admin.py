import csv
import hashlib
import io
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import hash_secret, require_admin
from app.db.models import (
    CodeSubmission,
    CodingContest,
    ExamLog,
    ExamSession,
    Question,
    Response,
    Student,
)
from app.db.session import get_db
from app.schemas.coding import ExamHistoryOut
from app.schemas.student import (
    CsvUploadResult,
    InviteBatchResult,
    InviteFailure,
    PinGenerationResult,
    PinRecord,
    StudentCsvRow,
    StudentImportResult,
)
from app.services.email_service import validate_email_settings, EmailConfigurationError, EmailDeliveryError
from app.services.excel_service import generate_excel_report
from app.services.invite_service import (
    build_exam_invite_link,
    create_invite_token,
    hash_invite_token,
    send_exam_invite_email,
)
from app.services.student_import_service import (
    ImportedStudentRow,
    StudentSheetValidationError,
    parse_student_sheet,
)

router = APIRouter(prefix="/admin", tags=["admin"])
PIN_ALPHABET = string.ascii_uppercase + string.digits
ROLL_NO_SAFE = re.compile(r"[^A-Z0-9]+")
AI_CHEATING_EVENTS = {
    "FACE_MISSING",
    "LOOKING_AWAY",
    "MULTIPLE_FACES",
}


@dataclass
class InviteJob:
    student: Student
    email: str
    name: str
    token: str
    pin: str
    expires_at: datetime


def _ensure_invite_email_configured() -> None:
    try:
        validate_email_settings()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


def _normalize_header(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _normalize_csv_row(raw: dict[str, str]) -> dict[str, str]:
    return {
        _normalize_header(key): (value or "").strip()
        for key, value in raw.items()
        if key is not None
    }


def _first_value(row: dict[str, str], aliases: tuple[str, ...]) -> str:
    for alias in aliases:
        value = row.get(alias)
        if value:
            return value
    return ""


def _clean_validation_errors(exc: ValidationError) -> list[dict[str, object]]:
    return [
        {
            "loc": error.get("loc", []),
            "msg": error.get("msg", "Invalid value."),
            "type": error.get("type", "validation_error"),
        }
        for error in exc.errors()
    ]


def _new_pin(used_pins: set[str]) -> str:
    while True:
        pin = "".join(secrets.choice(PIN_ALPHABET) for _ in range(6))
        if pin not in used_pins:
            used_pins.add(pin)
            return pin


def _generated_roll_no(email: str, reserved_roll_numbers: set[str]) -> str:
    local_part = email.split("@", 1)[0].upper()
    prefix = ROLL_NO_SAFE.sub("", local_part)[:20] or "STUDENT"
    digest = hashlib.sha1(email.encode("utf-8")).hexdigest()[:8].upper()
    base = f"{prefix}-{digest}"[:50]
    candidate = base
    counter = 2

    while candidate in reserved_roll_numbers:
        suffix = f"-{counter}"
        candidate = f"{base[:50 - len(suffix)]}{suffix}"
        counter += 1

    reserved_roll_numbers.add(candidate)
    return candidate


def _queue_invites(students: list[Student]) -> list[InviteJob]:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=settings.EXAM_INVITE_EXPIRE_HOURS
    )
    used_hashes: set[str] = set()
    used_pins: set[str] = set()
    jobs: list[InviteJob] = []

    for student in students:
        while True:
            token = create_invite_token()
            token_hash = hash_invite_token(token)
            if token_hash not in used_hashes:
                used_hashes.add(token_hash)
                break

        pin = _new_pin(used_pins)
        student.secret_pin = hash_secret(pin)
        student.is_pin_used = False
        student.invite_token_hash = token_hash
        student.invite_token_expires_at = expires_at
        student.invite_sent_at = None
        student.invite_accepted_at = None
        student.is_invite_used = False
        jobs.append(
            InviteJob(
                student=student,
                email=student.email,
                name=student.name,
                token=token,
                pin=pin,
                expires_at=expires_at,
            )
        )

    return jobs


async def _send_invite_jobs(jobs: list[InviteJob]) -> tuple[int, list[InviteFailure]]:
    try:
        validate_email_settings()
    except RuntimeError as exc:
        return 0, [InviteFailure(email=job.email, error=str(exc)) for job in jobs]

    sent = 0
    failures: list[InviteFailure] = []

    for job in jobs:
        invite_link = build_exam_invite_link(job.token)
        try:
            await run_in_threadpool(
                send_exam_invite_email,
                job.email,
                job.name,
                invite_link,
                job.pin,
                job.expires_at,
            )
        except Exception as exc:
            failures.append(InviteFailure(email=job.email, error=str(exc)))
            continue

        job.student.invite_sent_at = datetime.now(timezone.utc)
        sent += 1

    return sent, failures


async def _send_invite_jobs_background(jobs: list[InviteJob]) -> None:
    """Fire‑and‑forget email sending for background tasks."""
    try:
        validate_email_settings()
    except EmailConfigurationError as exc:
        logger.error("Email not configured: %s", exc)
        return
    except RuntimeError:
        return

    for job in jobs:
        invite_link = build_exam_invite_link(job.token)
        try:
            await run_in_threadpool(
                send_exam_invite_email,
                job.email,
                job.name,
                invite_link,
                job.pin,
                job.expires_at,
            )
        except EmailConfigurationError as exc:
            logger.error("SMTP configuration error for %s: %s", job.email, exc)
        except EmailDeliveryError as exc:
            logger.error("SMTP delivery error for %s: %s", job.email, exc)
        except Exception as exc:
            logger.error("Unexpected error sending invite to %s: %s", job.email, exc)


async def _upsert_imported_students(
    rows: list[ImportedStudentRow],
    db: AsyncSession,
) -> tuple[int, int, list[Student]]:
    emails = [str(row.email) for row in rows]
    existing_by_email: dict[str, Student] = {}
    email_result = await db.execute(
        select(Student).where(func.lower(Student.email).in_(emails))
    )
    for student in email_result.scalars().all():
        email = student.email.strip().lower()
        if email in existing_by_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Multiple existing students use email {email}.",
            )
        existing_by_email[email] = student

    provided_roll_numbers = [row.roll_no for row in rows if row.roll_no]
    existing_by_roll: dict[str, Student] = {}
    if provided_roll_numbers:
        roll_result = await db.execute(
            select(Student).where(Student.roll_no.in_(provided_roll_numbers))
        )
        existing_by_roll = {
            student.roll_no: student for student in roll_result.scalars().all()
        }

    roll_result = await db.execute(select(Student.roll_no))
    reserved_roll_numbers = set(roll_result.scalars().all())

    inserted = 0
    updated = 0
    imported_students: list[Student] = []

    for row in rows:
        email = str(row.email)
        existing = existing_by_email.get(email)

        if row.roll_no:
            roll_owner = existing_by_roll.get(row.roll_no)
            if roll_owner and existing and roll_owner.id != existing.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Row {row.row_number} email and roll_no belong to "
                        "different existing students."
                    ),
                )
            if roll_owner and not existing:
                existing = roll_owner

        if existing:
            existing.name = row.name
            existing.email = email
            existing.invite_status = "PENDING"
            if row.roll_no and existing.roll_no != row.roll_no:
                reserved_roll_numbers.discard(existing.roll_no)
                existing.roll_no = row.roll_no
                reserved_roll_numbers.add(row.roll_no)
                existing_by_roll[row.roll_no] = existing
            existing_by_email[email] = existing
            imported_students.append(existing)
            updated += 1
            continue

        roll_no = row.roll_no or _generated_roll_no(email, reserved_roll_numbers)
        if row.roll_no:
            reserved_roll_numbers.add(roll_no)

        student = Student(
            roll_no=roll_no,
            name=row.name,
            email=email,
            secret_pin=None,
            is_pin_used=False,
            invite_status="PENDING",
        )
        db.add(student)
        existing_by_email[email] = student
        existing_by_roll[roll_no] = student
        imported_students.append(student)
        inserted += 1

    return inserted, updated, imported_students


def _iso(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.isoformat(timespec="seconds")


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _contest_status(contest: CodingContest, now: datetime) -> str:
    start_time = _as_aware_utc(contest.start_time)
    end_time = _as_aware_utc(contest.end_time)
    if now < start_time:
        return "LOCKED"
    if now < end_time:
        return "ACTIVE"
    return "ENDED"


def _report_filename(contest: CodingContest | None = None) -> str:
    if contest is None:
        return "Exam_Report.xlsx"

    safe_title = re.sub(r"[^A-Za-z0-9]+", "_", contest.title).strip("_")
    safe_title = safe_title[:48] or "Exam"
    start_date = _as_aware_utc(contest.start_time).strftime("%Y%m%d_%H%M")
    return f"Exam_Report_{contest.id}_{safe_title}_{start_date}.xlsx"


def _log_details(log: ExamLog | None) -> dict[str, object]:
    if not log or not log.details:
        return {}
    try:
        loaded = json.loads(log.details)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _nested_details(details: dict[str, object]) -> dict[str, object]:
    nested = details.get("details")
    return nested if isinstance(nested, dict) else {}


def _client_time(details: dict[str, object]) -> str:
    nested = _nested_details(details)
    return str(details.get("client_timestamp") or nested.get("client_local_timestamp") or "")


def _client_timezone(details: dict[str, object]) -> str:
    nested = _nested_details(details)
    return str(nested.get("client_timezone") or details.get("client_timezone") or "")


def _cheat_direction(details: dict[str, object]) -> str:
    nested = _nested_details(details)
    return str(nested.get("direction") or details.get("direction") or "")


def _build_report_rows(
    students: list[Student],
    sessions: list[ExamSession],
    responses: list[tuple[Response, Question]],
    logs: list[ExamLog],
    questions: list[Question],
    submissions: list[CodeSubmission] | None = None,
    contest: CodingContest | None = None,
) -> list[dict[str, object]]:
    latest_session_by_student: dict[int, ExamSession] = {}
    for session in sessions:
        current = latest_session_by_student.get(session.student_id)
        if current is None or session.start_time > current.start_time:
            latest_session_by_student[session.student_id] = session

    logs_by_student: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    mobile_detected_at_by_student: dict[int, datetime] = {}
    mobile_blocked_at_by_student: dict[int, datetime] = {}
    ai_logs_by_student: dict[int, list[ExamLog]] = defaultdict(list)
    for log in logs:
        logs_by_student[log.student_id][log.event_type] += 1
        if log.event_type == "MOBILE_DEVICE_DETECTED":
            current = mobile_detected_at_by_student.get(log.student_id)
            if current is None or log.timestamp < current:
                mobile_detected_at_by_student[log.student_id] = log.timestamp
        if log.event_type == "MOBILE_DEVICE_BLOCKED":
            current = mobile_blocked_at_by_student.get(log.student_id)
            if current is None or log.timestamp < current:
                mobile_blocked_at_by_student[log.student_id] = log.timestamp
        if log.event_type in AI_CHEATING_EVENTS:
            ai_logs_by_student[log.student_id].append(log)

    responses_by_student: dict[int, list[tuple[Response, Question]]] = defaultdict(list)
    for response, question in responses:
        responses_by_student[response.student_id].append((response, question))

    latest_submission_by_student: dict[int, CodeSubmission] = {}
    submission_count_by_student: dict[int, int] = defaultdict(int)
    for submission in submissions or []:
        submission_count_by_student[submission.student_id] += 1
        current = latest_submission_by_student.get(submission.student_id)
        if current is None or submission.submitted_at > current.submitted_at:
            latest_submission_by_student[submission.student_id] = submission

    question_ids = [question.id for question in questions]
    total_questions = len(question_ids)
    rows: list[dict[str, object]] = []

    for student in students:
        latest_session = latest_session_by_student.get(student.id)
        student_responses = responses_by_student.get(student.id, [])
        correct_count = sum(
            1
            for response, question in student_responses
            if response.selected_option.upper() == question.correct_option.upper()
        )

        row: dict[str, object] = {
            "roll_no": student.roll_no,
            "name": student.name,
            "email": student.email,
            "pin_used": student.is_pin_used,
            "invite_sent_at": _iso(student.invite_sent_at),
            "invite_accepted_at": _iso(student.invite_accepted_at),
            "invite_expires_at": _iso(student.invite_token_expires_at),
            "score": correct_count,
            "total_questions": total_questions,
            "score_percent": round((correct_count / total_questions) * 100, 2)
            if total_questions
            else 0,
            "ip_address": latest_session.ip_address if latest_session else "",
            "location": latest_session.location if latest_session else "",
            "network_isp": latest_session.network_isp if latest_session else "",
            "latest_session_id": latest_session.id if latest_session else "",
            "exam_start_time": _iso(latest_session.start_time if latest_session else None),
            "exam_end_time": _iso(latest_session.end_time if latest_session else None),
            "tab_switch_count": logs_by_student[student.id].get("TAB_SWITCH", 0),
            "fullscreen_exit_count": logs_by_student[student.id].get("FULLSCREEN_EXIT", 0),
            "ip_mismatch_count": logs_by_student[student.id].get("IP_MISMATCH", 0),
            "blocked_key_count": logs_by_student[student.id].get("BLOCKED_KEY", 0),
            "camera_started_count": logs_by_student[student.id].get("CAMERA_STARTED", 0),
            "camera_error_count": logs_by_student[student.id].get("CAMERA_ERROR", 0),
            "focus_lost_count": logs_by_student[student.id].get("FOCUS_LOST", 0),
            "mobile_device_detected_count": logs_by_student[student.id].get(
                "MOBILE_DEVICE_DETECTED",
                0,
            ),
            "mobile_device_blocked_count": logs_by_student[student.id].get(
                "MOBILE_DEVICE_BLOCKED",
                0,
            ),
            "mobile_device_first_detected_at": _iso(
                mobile_detected_at_by_student.get(student.id)
            ),
            "mobile_device_first_blocked_at": _iso(
                mobile_blocked_at_by_student.get(student.id)
            ),
        }

        if contest:
            row.update(
                {
                    "exam_id": contest.id,
                    "exam_title": contest.title,
                    "exam_scheduled_start": _iso(_as_aware_utc(contest.start_time)),
                    "exam_scheduled_end": _iso(_as_aware_utc(contest.end_time)),
                }
            )

        if submissions is not None:
            latest_submission = latest_submission_by_student.get(student.id)
            row.update(
                {
                    "coding_attempts": submission_count_by_student.get(student.id, 0),
                    "latest_code_submission_id": latest_submission.id
                    if latest_submission
                    else "",
                    "coding_submitted_at": _iso(
                        latest_submission.submitted_at if latest_submission else None
                    ),
                    "coding_language": latest_submission.language
                    if latest_submission
                    else "",
                    "coding_status": latest_submission.status
                    if latest_submission
                    else "NOT_SUBMITTED",
                    "coding_score": latest_submission.score if latest_submission else 0,
                    "coding_passed_cases": latest_submission.passed_cases
                    if latest_submission
                    else 0,
                    "coding_total_cases": latest_submission.total_cases
                    if latest_submission
                    else 0,
                    "coding_auto_submitted": latest_submission.is_auto_submitted
                    if latest_submission
                    else False,
                    "exam_score": latest_submission.score if latest_submission else 0,
                    "exam_result_status": latest_submission.status
                    if latest_submission
                    else "NOT_SUBMITTED",
                }
            )

        ai_logs = ai_logs_by_student.get(student.id, [])
        first_ai_log = ai_logs[0] if ai_logs else None
        latest_ai_log = ai_logs[-1] if ai_logs else None
        first_ai_details = _log_details(first_ai_log)
        latest_ai_details = _log_details(latest_ai_log)
        row.update(
            {
                "ai_cheating_detected_count": len(ai_logs),
                "looking_away_count": logs_by_student[student.id].get("LOOKING_AWAY", 0),
                "face_missing_count": logs_by_student[student.id].get("FACE_MISSING", 0),
                "multiple_faces_count": logs_by_student[student.id].get("MULTIPLE_FACES", 0),
                "ai_first_event_type": first_ai_log.event_type if first_ai_log else "",
                "ai_first_server_time": _iso(first_ai_log.timestamp if first_ai_log else None),
                "ai_first_client_time": _client_time(first_ai_details),
                "ai_first_client_timezone": _client_timezone(first_ai_details),
                "ai_first_direction": _cheat_direction(first_ai_details),
                "ai_latest_event_type": latest_ai_log.event_type if latest_ai_log else "",
                "ai_latest_server_time": _iso(
                    latest_ai_log.timestamp if latest_ai_log else None
                ),
                "ai_latest_client_time": _client_time(latest_ai_details),
                "ai_latest_client_timezone": _client_timezone(latest_ai_details),
                "ai_latest_direction": _cheat_direction(latest_ai_details),
            }
        )

        response_by_question = {
            response.question_id: response
            for response, _question in student_responses
        }
        for question_id in question_ids:
            response = response_by_question.get(question_id)
            row[f"Q{question_id}_selected_option"] = (
                response.selected_option if response else ""
            )
            row[f"Q{question_id}_submitted_at"] = _iso(response.timestamp if response else None)

        rows.append(row)

    return rows


@router.post("/import-students", response_model=None)
async def import_students_sheet(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    send_invites: bool = Form(True),
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, object] = Depends(require_admin),
):
    try:
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please upload a student sheet.",
            )

        content = await file.read()
        try:
            rows = await run_in_threadpool(parse_student_sheet, content, file.filename)
        except StudentSheetValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"message": exc.message, "errors": exc.errors},
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        # Deduplicate rows by email (case-insensitive) keeping first occurrence
        seen_emails = set()
        dedup_rows = []
        for row in rows:
            email_key = str(row.email).strip().lower()
            if not email_key:
                continue  # skip rows without email
            if email_key in seen_emails:
                continue
            seen_emails.add(email_key)
            dedup_rows.append(row)

        inserted, updated, students = await _upsert_imported_students(dedup_rows, db)

        invite_jobs = _queue_invites(students) if send_invites else []

        # Commit student records (including invite tokens/pins)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            # Resolve conflicts by updating existing records for each student
            for stu in students:
                if stu.id is None:
                    result = await db.execute(
                        select(Student).where(func.lower(Student.email) == stu.email.lower())
                    )
                    existing = result.scalars().first()
                    if existing:
                        existing.name = stu.name
                        existing.roll_no = stu.roll_no
                        students[students.index(stu)] = existing
                        updated += 1
                        inserted -= 1
            await db.commit()

        # If invites requested, dispatch emails in background
        if invite_jobs:
            background_tasks.add_task(_send_invite_jobs_background, invite_jobs)

        return {
            "status": "success",
            "message": "Students imported successfully. Invites are being dispatched in the background.",
            "inserted": inserted,
            "updated": updated,
            "total_students": len(students),
            "invites_sent": 0,
            "invites_failed": 0,
            "failed_invites": [],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {exc}",
        ) from exc


@router.post("/send-invites", response_model=None)
async def send_student_invites(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, object] = Depends(require_admin),
):
    try:
        result = await db.execute(
            select(Student)
            .where(or_(Student.invite_status == "PENDING", Student.invite_status.is_(None)))
            .order_by(Student.roll_no)
        )
        students = result.scalars().all()
        if not students:
            return {
                "status": "warning",
                "message": "No pending students found to send invites. Please upload a student CSV first.",
                "sent": 0,
                "failed": 0,
            }

        _ensure_invite_email_configured()
        invite_jobs = _queue_invites(students)
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Invite generation conflicts with existing database constraints.",
            ) from exc

        # Dispatch emails in background
        background_tasks.add_task(_send_invite_jobs_background, invite_jobs)

        return {
            "status": "success",
            "message": "Invite emails are being dispatched in the background.",
            "sent": 0,
            "failed": 0,
            "failed_invites": [],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send invites: {exc}",
        ) from exc


@router.post("/upload-csv", response_model=CsvUploadResult)
async def upload_students_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, object] = Depends(require_admin),
) -> CsvUploadResult:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload a .csv file.",
        )

    content = await file.read()
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV must be encoded as UTF-8.",
        ) from exc

    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV header row is missing.",
        )

    students_by_roll: dict[str, StudentCsvRow] = {}
    errors: list[dict[str, object]] = []

    for row_number, raw_row in enumerate(reader, start=2):
        row = _normalize_csv_row(raw_row)
        try:
            student = StudentCsvRow(
                row_number=row_number,
                roll_no=_first_value(row, ("roll_no", "roll", "roll_number")),
                name=_first_value(row, ("name", "student_name", "full_name")),
                email=_first_value(row, ("email", "email_id", "student_email")),
            )
        except ValidationError as exc:
            errors.append(
                {
                    "row": row_number,
                    "errors": _clean_validation_errors(exc),
                }
            )
            continue

        if student.roll_no in students_by_roll:
            errors.append(
                {
                    "row": row_number,
                    "errors": [
                        {
                            "loc": ["roll_no"],
                            "msg": f"Duplicate roll_no {student.roll_no} in CSV.",
                            "type": "duplicate_roll_no",
                        }
                    ],
                }
            )
            continue

        students_by_roll[student.roll_no] = student

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Invalid student CSV rows.", "errors": errors},
        )

    if not students_by_roll:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV does not contain any student rows.",
        )

    roll_numbers = list(students_by_roll)
    result = await db.execute(select(Student).where(Student.roll_no.in_(roll_numbers)))
    existing_by_roll = {student.roll_no: student for student in result.scalars().all()}

    inserted = 0
    updated = 0

    for student_row in students_by_roll.values():
        existing = existing_by_roll.get(student_row.roll_no)
        if existing:
            existing.name = student_row.name
            existing.email = str(student_row.email)
            updated += 1
        else:
            db.add(
                Student(
                    roll_no=student_row.roll_no,
                    name=student_row.name,
                    email=str(student_row.email),
                    secret_pin=None,
                    is_pin_used=False,
                )
            )
            inserted += 1

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student upload conflicts with existing database constraints.",
        ) from exc

    return CsvUploadResult(
        filename=file.filename,
        inserted=inserted,
        updated=updated,
        total_students=len(students_by_roll),
    )


@router.post("/generate-pins", response_model=PinGenerationResult)
async def generate_pins(
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, object] = Depends(require_admin),
) -> PinGenerationResult:
    result = await db.execute(select(Student).order_by(Student.roll_no))
    students = result.scalars().all()
    if not students:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload students before generating PINs.",
        )

    used_pins: set[str] = set()
    records: list[PinRecord] = []
    for student in students:
        pin = _new_pin(used_pins)
        student.secret_pin = hash_secret(pin)
        student.is_pin_used = False
        records.append(
            PinRecord(
                roll_no=student.roll_no,
                name=student.name,
                email=student.email,
                pin=pin,
            )
        )

    await db.commit()
    return PinGenerationResult(total_students=len(records), pins=records)


@router.get("/exam-history", response_model=list[ExamHistoryOut])
async def exam_history(
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, object] = Depends(require_admin),
) -> list[ExamHistoryOut]:
    contests = (
        await db.execute(select(CodingContest).order_by(CodingContest.start_time.desc()))
    ).scalars().all()
    if not contests:
        return []

    contest_ids = [contest.id for contest in contests]
    count_rows = await db.execute(
        select(
            CodeSubmission.contest_id,
            func.count(CodeSubmission.id),
            func.count(func.distinct(CodeSubmission.student_id)),
        )
        .where(CodeSubmission.contest_id.in_(contest_ids))
        .group_by(CodeSubmission.contest_id)
    )
    counts_by_contest = {
        contest_id: (int(total_submissions), int(students_submitted))
        for contest_id, total_submissions, students_submitted in count_rows.all()
    }
    now = datetime.now(timezone.utc)

    return [
        ExamHistoryOut(
            id=contest.id,
            title=contest.title,
            start_time=_as_aware_utc(contest.start_time),
            end_time=_as_aware_utc(contest.end_time),
            is_published=contest.is_published,
            status=_contest_status(contest, now),
            total_submissions=counts_by_contest.get(contest.id, (0, 0))[0],
            students_submitted=counts_by_contest.get(contest.id, (0, 0))[1],
        )
        for contest in contests
    ]


@router.get("/export")
async def export_excel_report(
    contest_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _admin: dict[str, object] = Depends(require_admin),
) -> FileResponse:
    contest: CodingContest | None = None
    if contest_id is not None:
        contest = await db.get(CodingContest, contest_id)
        if contest is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Exam not found.",
            )

    students = (
        await db.execute(select(Student).order_by(Student.roll_no))
    ).scalars().all()

    if contest:
        sessions = (
            await db.execute(
                select(ExamSession)
                .where(
                    ExamSession.start_time <= contest.end_time,
                    or_(
                        ExamSession.end_time.is_(None),
                        ExamSession.end_time >= contest.start_time,
                    ),
                )
                .order_by(ExamSession.start_time)
            )
        ).scalars().all()
        session_ids = [session.id for session in sessions]
        logs = (
            (
                await db.execute(
                    select(ExamLog)
                    .where(ExamLog.session_id.in_(session_ids))
                    .order_by(ExamLog.timestamp)
                )
            ).scalars().all()
            if session_ids
            else []
        )
        questions = []
        responses = []
        submissions = (
            await db.execute(
                select(CodeSubmission)
                .where(CodeSubmission.contest_id == contest.id)
                .order_by(CodeSubmission.student_id, CodeSubmission.submitted_at)
            )
        ).scalars().all()
    else:
        sessions = (
            await db.execute(select(ExamSession).order_by(ExamSession.start_time))
        ).scalars().all()
        logs = (
            await db.execute(select(ExamLog).order_by(ExamLog.timestamp))
        ).scalars().all()
        questions = (
            await db.execute(select(Question).order_by(Question.id))
        ).scalars().all()
        responses = (
            await db.execute(
                select(Response, Question)
                .join(Question, Response.question_id == Question.id)
                .order_by(Response.student_id, Response.question_id)
            )
        ).all()
        submissions = (
            await db.execute(
                select(CodeSubmission).order_by(
                    CodeSubmission.student_id,
                    CodeSubmission.contest_id,
                    CodeSubmission.submitted_at,
                )
            )
        ).scalars().all()

    rows = _build_report_rows(
        students,
        sessions,
        responses,
        logs,
        questions,
        submissions,
        contest,
    )
    filename = _report_filename(contest)
    report_path = await run_in_threadpool(
        generate_excel_report,
        rows,
        filename,
    )
    return FileResponse(
        report_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=report_path.name,
    )
