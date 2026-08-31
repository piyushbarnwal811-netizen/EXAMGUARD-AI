import asyncio
import json
from io import BytesIO
from datetime import datetime, timedelta, timezone

import httpx
from openpyxl import Workbook
from sqlalchemy import select

from app.api import contest as contest_api
from app.core.security import hash_secret, verify_secret
from app.db.models import CodingContest, CodingTestCase, ExamLog, Student
from app.db.session import AsyncSessionLocal
from app.services import coding_executor
from app.services.coding_executor import ExecutionCaseResult
from app.services.invite_service import hash_invite_token


def run(coro):
    return asyncio.run(coro)


async def _create_student(
    roll_no: str = "ROLL001",
    email: str = "student@example.com",
    pin: str | None = "ABC123",
    invite_token: str | None = None,
) -> int:
    now = datetime.now(timezone.utc)
    student = Student(
        roll_no=roll_no,
        name="Test Student",
        email=email,
        secret_pin=hash_secret(pin) if pin else None,
        is_pin_used=False,
        invite_token_hash=hash_invite_token(invite_token) if invite_token else None,
        invite_token_expires_at=now + timedelta(hours=1) if invite_token else None,
    )
    async with AsyncSessionLocal() as db:
        db.add(student)
        await db.commit()
        await db.refresh(student)
        return student.id


async def _activate_contest() -> None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(CodingContest).order_by(CodingContest.id.desc()))
        contest = result.scalars().first()
        contest.start_time = now - timedelta(minutes=5)
        contest.end_time = now + timedelta(minutes=30)
        contest.is_published = True
        await db.commit()


async def _end_contest() -> None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(CodingContest).order_by(CodingContest.id.desc()))
        contest = result.scalars().first()
        contest.start_time = now - timedelta(hours=1)
        contest.end_time = now - timedelta(minutes=1)
        contest.is_published = True
        await db.commit()


async def _latest_log(event_type: str) -> ExamLog | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ExamLog)
            .where(ExamLog.event_type == event_type)
            .order_by(ExamLog.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


def _student_token(client, roll_no: str = "ROLL001", pin: str = "ABC123") -> dict:
    response = client.post(
        "/api/auth/verify-pin",
        json={"roll_no": roll_no, "pin": pin},
    )
    assert response.status_code == 200
    return response.json()


def _admin_token(client) -> str:
    response = client.post(
        "/api/auth/admin-login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _generated_question_payload(
    title: str,
    statement: str,
    sample_input: str,
    sample_output: str,
) -> dict[str, object]:
    return {
        "title": title,
        "statement": statement,
        "sample_input": sample_input,
        "sample_output": sample_output,
        "test_cases": [
            {
                "input_data": sample_input if index == 0 else f"{sample_input}\ncase {index + 1}",
                "expected_output": sample_output
                if index == 0
                else f"{sample_output}\ncase {index + 1}",
                "is_visible": index < 2,
            }
            for index in range(10)
        ],
    }


def test_admin_and_student_login_create_session(client):
    admin_response = client.post(
        "/api/auth/admin-login",
        json={"username": "admin", "password": "admin123"},
    )
    assert admin_response.status_code == 200
    assert admin_response.json()["role"] == "admin"

    run(_create_student())
    student_data = _student_token(client)

    assert student_data["role"] == "student"
    assert student_data["student_id"] is not None
    assert student_data["session_id"] is not None

    second_login = client.post(
        "/api/auth/verify-pin",
        json={"roll_no": "ROLL001", "pin": "ABC123"},
    )
    assert second_login.status_code == 409


def test_invite_verification_starts_exam_session(client):
    invite_token = "invite-token-for-api-test-123456789"
    run(
        _create_student(
            roll_no="INV001",
            email="invite@example.com",
            pin="PIN789",
            invite_token=invite_token,
        )
    )

    missing_pin = client.post("/api/auth/verify-invite", json={"token": invite_token})
    assert missing_pin.status_code == 422

    response = client.post(
        "/api/auth/verify-invite",
        json={"token": invite_token, "pin": "PIN789"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "student"
    assert body["session_id"] is not None


def test_send_invites_generates_pin_and_email(client, monkeypatch):
    from app.api import admin as admin_api

    token = _admin_token(client)
    run(
        _create_student(
            roll_no="MAIL001",
            email="mail.student@example.com",
            pin=None,
        )
    )
    sent_messages = []

    def fake_send_invite_email(to_email, student_name, invite_link, pin, expires_at):
        sent_messages.append(
            {
                "to_email": to_email,
                "student_name": student_name,
                "invite_link": invite_link,
                "pin": pin,
                "expires_at": expires_at,
            }
        )

    monkeypatch.setattr(admin_api, "validate_email_settings", lambda: None)
    monkeypatch.setattr(admin_api, "send_exam_invite_email", fake_send_invite_email)

    response = client.post(
        "/api/admin/send-invites",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["invites_sent"] == 1
    assert body["invites_failed"] == 0
    assert len(sent_messages) == 1
    assert sent_messages[0]["to_email"] == "mail.student@example.com"
    assert len(sent_messages[0]["pin"]) == 6
    assert "invite=" in sent_messages[0]["invite_link"]

    async def fetch_student() -> Student:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Student).where(Student.roll_no == "MAIL001")
            )
            return result.scalar_one()

    student = run(fetch_student())
    assert student.secret_pin
    assert verify_secret(sent_messages[0]["pin"], student.secret_pin)
    assert student.invite_token_hash
    assert student.is_pin_used is False


def test_email_settings_are_sanitized_for_gmail_app_passwords():
    from app.services.email_service import (
        _clean_email_address,
        _clean_smtp_password,
        _smtp_from_header,
    )

    assert _clean_email_address("admin.sender@gmail.com          # personal Gmail") == (
        "admin.sender@gmail.com"
    )
    assert _clean_smtp_password("abcd efgh ijkl mnop          # app password") == (
        "abcdefghijklmnop"
    )
    assert _smtp_from_header(
        "ExamGuard <different@gmail.com>",
        "admin.sender@gmail.com",
        "smtp.gmail.com",
    ) == "ExamGuard <admin.sender@gmail.com>"


def test_admin_exam_history_lists_scheduled_exams(client):
    token = _admin_token(client)

    response = client.get(
        "/api/admin/exam-history",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body
    assert body[0]["title"] == "ExamGuard Pro Coding Contest"
    assert body[0]["total_submissions"] == 0
    assert body[0]["students_submitted"] == 0


def test_admin_can_generate_ai_questions(client, monkeypatch):
    from app.api import questions as questions_api

    token = _admin_token(client)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.6-flash")
    monkeypatch.setenv("GEMINI_REMOTE_ENABLED", "true")

    def fake_generate(api_key, payload, generation_id, model_name, timeout_seconds):
        assert api_key == "test-gemini-key"
        assert payload.topic == "Python OOP"
        assert payload.difficulty == "Medium"
        assert payload.count == 2
        assert generation_id
        assert model_name == "gemini-3.6-flash"
        assert timeout_seconds >= 30
        return questions_api._parse_questions(
            json.dumps(
                [
                    _generated_question_payload(
                        "Class Construction",
                        "Create a class and instantiate it.",
                        "Student Alice",
                        "Alice",
                    ),
                    _generated_question_payload(
                        "Inheritance Basics",
                        "Extend a base class and override a method.",
                        "Dog speak",
                        "Bark",
                    ),
                ]
            )
        )

    monkeypatch.setattr(questions_api, "_generate_questions_with_gemini", fake_generate)

    response = client.post(
        "/api/questions/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={"topic": "Python OOP", "difficulty": "medium", "count": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["topic"] == "Python OOP"
    assert body["difficulty"] == "Medium"
    assert body["count"] == 2
    assert body["source"] == "gemini"
    assert body["generation_id"]
    assert [item["title"] for item in body["questions"]] == [
        "Class Construction",
        "Inheritance Basics",
    ]
    assert all(len(item["test_cases"]) == 10 for item in body["questions"])


def test_admin_requires_gemini_key_for_ai_questions(client, monkeypatch):
    from types import SimpleNamespace

    from app.api import questions as questions_api

    token = _admin_token(client)
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setattr(
        questions_api,
        "get_settings",
        lambda: SimpleNamespace(GEMINI_API_KEY="", GEMINI_REMOTE_ENABLED=True),
    )

    response = client.post(
        "/api/questions/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={"topic": "Stacks", "difficulty": "easy", "count": 2},
    )

    assert response.status_code == 503
    body = response.json()
    assert "Gemini API key is not configured" in body["detail"]


def test_admin_ai_questions_fallback_when_gemini_fails(client, monkeypatch):
    from app.api import questions as questions_api

    token = _admin_token(client)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("GEMINI_REMOTE_ENABLED", "true")

    def fail_generate(*_args, **_kwargs):
        raise questions_api.GeminiResponseError("invalid Gemini response")

    monkeypatch.setattr(questions_api, "_generate_questions_with_gemini", fail_generate)

    response = client.post(
        "/api/questions/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={"topic": "Arrays", "difficulty": "easy", "count": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "local_fallback"
    assert body["count"] == 2
    assert len(body["questions"]) == 2
    assert all(len(item["test_cases"]) == 10 for item in body["questions"])
    assert all(
        sum(1 for case in item["test_cases"] if case["is_visible"]) == 2
        for item in body["questions"]
    )


def test_admin_excel_upload_imports_students_without_email(client):
    token = _admin_token(client)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["name", "email"])
    sheet.append(["Excel Student", "excel.student@example.com"])
    buffer = BytesIO()
    workbook.save(buffer)

    response = client.post(
        "/api/admin/import-students",
        headers={"Authorization": f"Bearer {token}"},
        data={"send_invites": "false"},
        files={
            "file": (
                "students.xlsx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["inserted"] == 1
    assert body["total_students"] == 1
    assert body["invites_sent"] == 0


def test_admin_can_update_coding_problem(client):
    token = _admin_token(client)
    test_cases = [
        {"input_data": "1 2", "expected_output": "3", "is_visible": True},
        {"input_data": "5 7", "expected_output": "12", "is_visible": True},
        {"input_data": "0 0", "expected_output": "0", "is_visible": False},
        {"input_data": "-1 4", "expected_output": "3", "is_visible": False},
        {"input_data": "10 20", "expected_output": "30", "is_visible": False},
        {"input_data": "100 1", "expected_output": "101", "is_visible": False},
        {"input_data": "8 -3", "expected_output": "5", "is_visible": False},
        {"input_data": "9 9", "expected_output": "18", "is_visible": False},
        {"input_data": "123 456", "expected_output": "579", "is_visible": False},
        {"input_data": "-10 -20", "expected_output": "-30", "is_visible": False},
    ]

    response = client.put(
        "/api/contest/problem-admin",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Add Two Values",
            "statement": "Read two values and print their sum.",
            "input_format": "Two integers.",
            "output_format": "Their sum.",
            "constraints": "-1000 <= values <= 1000",
            "starter_code_python": "print(sum(map(int, input().split())))",
            "starter_code_cpp": "#include <bits/stdc++.h>\nint main(){return 0;}",
            "starter_code_java": "public class Main { public static void main(String[] args) {} }",
            "enabled_languages": ["python"],
            "test_cases": test_cases,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Add Two Values"
    assert body["enabled_languages"] == ["python"]
    assert len(body["test_cases"]) == 10
    assert sum(1 for item in body["test_cases"] if item["is_visible"]) == 2


def test_admin_problem_save_does_not_publish_student_contest(client):
    run(_create_student())
    token_data = _student_token(client)
    admin_token = _admin_token(client)

    response = client.put(
        "/api/contest/problem-admin",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "title": "Masked Save Test",
            "statement": "This question should remain hidden until scheduled.",
            "input_format": "N/A",
            "output_format": "N/A",
            "constraints": "N/A",
            "starter_code_python": "print('hidden')",
            "starter_code_cpp": "int main(){return 0;}",
            "starter_code_java": "class Main { }",
            "test_cases": [
                {"input_data": "1", "expected_output": "1", "is_visible": True},
                {"input_data": "2", "expected_output": "2", "is_visible": True},
                {"input_data": "3", "expected_output": "3", "is_visible": False},
                {"input_data": "4", "expected_output": "4", "is_visible": False},
                {"input_data": "5", "expected_output": "5", "is_visible": False},
                {"input_data": "6", "expected_output": "6", "is_visible": False},
                {"input_data": "7", "expected_output": "7", "is_visible": False},
                {"input_data": "8", "expected_output": "8", "is_visible": False},
                {"input_data": "9", "expected_output": "9", "is_visible": False},
                {"input_data": "10", "expected_output": "10", "is_visible": False},
            ],
        },
    )

    assert response.status_code == 200

    student_status = client.get(
        "/api/contest/status",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
    )

    assert student_status.status_code == 200
    body = student_status.json()
    assert body.get("problem") is None
    assert body["status"] in {"LOCKED", "ENDED"}


def test_contest_status_returns_active_problem_for_student(client):
    run(_create_student())
    token_data = _student_token(client)
    run(_activate_contest())

    response = client.get(
        "/api/contest/status",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ACTIVE"
    assert body["problem"]["title"] == "Sum of Two Numbers"


def test_saved_draft_can_be_auto_submitted(client, monkeypatch):
    async def fake_execute(source_code, language, test_cases):
        return [
            ExecutionCaseResult(
                case_number=test_case.sort_order,
                is_visible=test_case.is_visible,
                passed=True,
                input_data=test_case.input_data,
                expected_output=test_case.expected_output,
                actual_output=test_case.expected_output,
                error_logs="",
            )
            for test_case in test_cases
        ]

    monkeypatch.setattr(contest_api, "execute_code_against_cases", fake_execute)
    run(_create_student())
    token_data = _student_token(client)
    run(_activate_contest())
    headers = {"Authorization": f"Bearer {token_data['access_token']}"}

    status_response = client.get("/api/contest/status", headers=headers)
    assert status_response.status_code == 200
    problem_id = status_response.json()["problem"]["id"]

    draft_response = client.put(
        "/api/contest/draft",
        headers=headers,
        json={
            "problem_id": problem_id,
            "language": "python",
            "source_code": "print('saved draft')",
        },
    )
    assert draft_response.status_code == 200
    assert draft_response.json()["saved"] is True

    submit_response = client.post(
        "/api/contest/auto-submit-draft",
        headers=headers,
        json={"problem_id": problem_id, "reason": "pagehide"},
    )
    assert submit_response.status_code == 200
    body = submit_response.json()
    assert body["submitted"] is True
    assert body["score"] == 100
    assert body["submission_id"] is not None


def test_contest_status_shows_final_marks_after_exam_ends(client, monkeypatch):
    async def fake_execute(source_code, language, test_cases):
        return [
            ExecutionCaseResult(
                case_number=test_case.sort_order,
                is_visible=test_case.is_visible,
                passed=True,
                input_data=test_case.input_data,
                expected_output=test_case.expected_output,
                actual_output=test_case.expected_output,
                error_logs="",
            )
            for test_case in test_cases
        ]

    monkeypatch.setattr(contest_api, "execute_code_against_cases", fake_execute)
    run(_create_student())
    token_data = _student_token(client)
    run(_activate_contest())
    headers = {"Authorization": f"Bearer {token_data['access_token']}"}

    status_response = client.get("/api/contest/status", headers=headers)
    assert status_response.status_code == 200
    problem_id = status_response.json()["problem"]["id"]

    submit_response = client.post(
        "/api/contest/submit",
        headers=headers,
        json={
            "problem_id": problem_id,
            "language": "python",
            "source_code": "print('final marks')",
            "auto_submitted": False,
        },
    )
    assert submit_response.status_code == 200

    run(_end_contest())
    ended_response = client.get("/api/contest/status", headers=headers)

    assert ended_response.status_code == 200
    body = ended_response.json()
    assert body["status"] == "ENDED"
    assert body["final_result"]["score"] == 100
    assert body["final_result"]["passed_cases"] == 10
    assert body["final_result"]["total_cases"] == 10


def test_tracking_event_is_timestamped_and_session_scoped(client):
    run(_create_student())
    token_data = _student_token(client)

    response = client.post(
        "/api/tracking/events",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
        json={
            "event_type": "CAMERA_STARTED",
            "message": "Camera stream started.",
            "client_timestamp": "2026-08-02T10:00:00+00:00",
            "details": {"width": 640, "height": 480},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "logged"
    assert body["session_id"] == token_data["session_id"]
    assert "timestamp" in body

    log = run(_latest_log("CAMERA_STARTED"))
    assert log is not None
    assert log.session_id == token_data["session_id"]
    details = json.loads(log.details)
    assert details["session_id"] == token_data["session_id"]
    assert details["client_timestamp"] == "2026-08-02T10:00:00Z"

    ai_response = client.post(
        "/api/tracking/events",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
        json={
            "event_type": "LOOKING_AWAY",
            "message": "Camera AI detected suspicious exam behavior.",
            "client_timestamp": "2026-08-02T10:05:00+05:30",
            "details": {
                "direction": "LEFT",
                "client_timezone": "Asia/Calcutta",
            },
        },
    )

    assert ai_response.status_code == 200
    assert ai_response.json()["event_type"] == "LOOKING_AWAY"


def test_python_code_uses_local_fallback_when_executor_is_unavailable(monkeypatch):
    async def fail_post(*_args, **_kwargs):
        request = httpx.Request("POST", "http://executor.local/execute")
        raise httpx.ConnectError("offline", request=request)

    monkeypatch.setattr(coding_executor.httpx.AsyncClient, "post", fail_post)
    test_case = CodingTestCase(
        input_data="2 3",
        expected_output="5",
        is_visible=True,
        sort_order=1,
    )

    results = run(
        coding_executor.execute_code_against_cases(
            "print(sum(map(int, input().split())))",
            "python",
            [test_case],
        )
    )

    assert results[0].passed is True
    assert results[0].actual_output.strip() == "5"
