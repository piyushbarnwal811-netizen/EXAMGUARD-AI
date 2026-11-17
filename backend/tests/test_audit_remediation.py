import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DB_PATH = BACKEND_DIR / "test_remediation.db"

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["SECRET_KEY"] = "examguard-audit-secret-key"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin123"
os.environ["ALLOWED_IP_RANGES"] = "127.0.0.1/32,::1/128"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token, decode_access_token
from app.db.models import Base, ExamSession, Question, Response, Student
from app.db.session import AsyncSessionLocal, engine, init_db
from app.main import app


async def setup_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await init_db()

    # Seed 3 test questions
    async with AsyncSessionLocal() as db:
        q1 = Question(
            question_text="What is Python?",
            option_a="Snake",
            option_b="Programming Language",
            option_c="Coffee",
            option_d="Browser",
            correct_option="B",
        )
        q2 = Question(
            question_text="Which complexity is fastest?",
            option_a="O(n^2)",
            option_b="O(n)",
            option_c="O(1)",
            option_d="O(n log n)",
            correct_option="C",
        )
        q3 = Question(
            question_text="Which protocol is encrypted?",
            option_a="HTTP",
            option_b="FTP",
            option_c="HTTPS",
            option_d="TELNET",
            correct_option="C",
        )
        db.add_all([q1, q2, q3])
        await db.commit()


def test_bug_006_role_based_access_control():
    """Verify BUG-006: Unauthorized users and students are strictly blocked from admin reports & interventions."""
    client = TestClient(app)

    # 1. Unauthenticated request to report endpoint -> 401 Unauthorized
    res = client.get("/api/v1/proctor/sessions/1/report")
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"

    # 2. Student token trying to access admin report -> 403 Forbidden
    student_token = create_access_token({"sub": "ROLL-101", "role": "student", "student_id": 1})
    res = client.get(
        "/api/v1/proctor/sessions/1/report",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert res.status_code == 403, f"Expected 403 for student role, got {res.status_code}"

    # 3. Unauthenticated request to live intervention endpoint -> 401 Unauthorized
    res = client.post(
        "/api/v1/invigilator/test-exam/intervene",
        json={"action": "TERMINATE", "sessionId": "sess_123"},
    )
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"

    # 4. Student token trying to trigger intervention -> 403 Forbidden
    res = client.post(
        "/api/v1/invigilator/test-exam/intervene",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"action": "TERMINATE", "sessionId": "sess_123"},
    )
    assert res.status_code == 403, f"Expected 403 for student role, got {res.status_code}"

    # 5. Admin token allowed to access intervention
    admin_token = create_access_token({"sub": "admin", "role": "admin"})
    res = client.post(
        "/api/v1/invigilator/test-exam/intervene",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"action": "WARN", "sessionId": "sess_123", "message": "Test warning"},
    )
    assert res.status_code == 200, f"Expected 200 for admin, got {res.status_code}"
    print("✔ test_bug_006_role_based_access_control PASSED")


def test_bug_002_post_submission_answer_lock():
    """Verify BUG-002: Answers cannot be submitted or changed after exam finalization."""
    client = TestClient(app)

    # Onboard student
    res = client.post(
        "/api/auth/coaching-candidate-onboard",
        json={
            "name": "Aman Verma",
            "roll_no": "ROLL-AMAN-01",
            "coaching_name": "Target Topper Classes",
            "exam_id": "testing-2",
        },
    )
    assert res.status_code == 200
    data = res.json()
    token = data["access_token"]
    student_headers = {"Authorization": f"Bearer {token}"}

    # Submit answer while active -> Should succeed (200)
    ans_res = client.post(
        "/api/exam/answers",
        headers=student_headers,
        json={"question_id": 1, "selected_option": "B"},
    )
    assert ans_res.status_code == 200
    assert ans_res.json()["saved"] is True

    # Finalize / Submit Exam
    end_res = client.post(
        "/api/exam/timestamp?event=EXAM_END",
        headers=student_headers,
    )
    assert end_res.status_code == 200

    # Attempt to change or submit answers AFTER submission -> Must return 403 Forbidden!
    tamper_res = client.post(
        "/api/exam/answers",
        headers=student_headers,
        json={"question_id": 1, "selected_option": "A"},
    )
    assert tamper_res.status_code == 403, f"Expected 403 after submit, got {tamper_res.status_code}"
    assert "already been submitted" in tamper_res.json()["detail"].lower()
    print("✔ test_bug_002_post_submission_answer_lock PASSED")


def test_bug_008_server_session_status_and_timer():
    """Verify BUG-008: Server-side session status returns authoritative remaining seconds and submit status."""
    client = TestClient(app)

    # Onboard new student
    res = client.post(
        "/api/auth/coaching-candidate-onboard",
        json={
            "name": "Priya Sharma",
            "roll_no": "ROLL-PRIYA-02",
            "coaching_name": "Target Topper Classes",
            "exam_id": "testing-2",
        },
    )
    token = res.json()["access_token"]
    student_headers = {"Authorization": f"Bearer {token}"}

    # Check status during exam
    status_res = client.get("/api/exam/session-status", headers=student_headers)
    assert status_res.status_code == 200
    s_data = status_res.json()
    assert s_data["is_submitted"] is False
    assert s_data["remaining_seconds"] > 0
    assert s_data["duration_minutes"] == 60
    assert "candidate_name" in s_data

    # Submit exam
    client.post("/api/exam/timestamp?event=EXAM_END", headers=student_headers)

    # Check status after exam submit
    post_submit_status = client.get("/api/exam/session-status", headers=student_headers)
    assert post_submit_status.status_code == 200
    ps_data = post_submit_status.json()
    assert ps_data["is_submitted"] is True
    assert ps_data["remaining_seconds"] == 0
    assert ps_data["submitted_at"] is not None
    print("✔ test_bug_008_server_session_status_and_timer PASSED")


def test_bug_001_answer_persistence_and_sync():
    """Verify BUG-001: Backend allows recovering all saved answers via /api/exam/my-answers."""
    client = TestClient(app)

    res = client.post(
        "/api/auth/coaching-candidate-onboard",
        json={
            "name": "Rahul Kumar",
            "roll_no": "ROLL-RAHUL-03",
            "coaching_name": "Target Topper Classes",
            "exam_id": "testing-2",
        },
    )
    token = res.json()["access_token"]
    student_headers = {"Authorization": f"Bearer {token}"}

    # Submit 2 answers
    client.post("/api/exam/answers", headers=student_headers, json={"question_id": 1, "selected_option": "B"})
    client.post("/api/exam/answers", headers=student_headers, json={"question_id": 2, "selected_option": "C"})

    # Fetch saved answers
    my_res = client.get("/api/exam/my-answers", headers=student_headers)
    assert my_res.status_code == 200
    ans_data = my_res.json()
    assert ans_data["total_answered"] == 2
    assert ans_data["answers"]["1"] == "B"
    assert ans_data["answers"]["2"] == "C"
    print("✔ test_bug_001_answer_persistence_and_sync PASSED")


def test_bug_003_prevent_duplicate_attempts():
    """Verify BUG-003: A student cannot onboard again and take the exam twice after submitting."""
    client = TestClient(app)

    roll = "ROLL-DUPLICATE-04"
    # 1. Onboard
    res1 = client.post(
        "/api/auth/coaching-candidate-onboard",
        json={
            "name": "Sameer Singh",
            "roll_no": roll,
            "coaching_name": "Target Topper Classes",
            "exam_id": "testing-2",
        },
    )
    assert res1.status_code == 200
    token = res1.json()["access_token"]

    # 2. Complete and Submit
    client.post("/api/exam/timestamp?event=EXAM_END", headers={"Authorization": f"Bearer {token}"})

    # 3. Try to onboard again with the same roll number -> Expect 409 Conflict!
    res2 = client.post(
        "/api/auth/coaching-candidate-onboard",
        json={
            "name": "Sameer Singh",
            "roll_no": roll,
            "coaching_name": "Target Topper Classes",
            "exam_id": "testing-2",
        },
    )
    assert res2.status_code == 409, f"Expected 409 Conflict, got {res2.status_code}"
    assert "already completed" in res2.json()["detail"].lower()
    print("✔ test_bug_003_prevent_duplicate_attempts PASSED")


def test_bug_007_concurrent_onboarding_safety():
    """Verify BUG-007: Multiple onboarding attempts for the same student do not raise 500 error."""
    client = TestClient(app)

    roll = "ROLL-CONCURRENT-05"
    payload = {
        "name": "Ananya Roy",
        "roll_no": roll,
        "coaching_name": "Target Topper Classes",
        "exam_id": "testing-2",
    }

    # First attempt creates the student
    r1 = client.post("/api/auth/coaching-candidate-onboard", json=payload)
    assert r1.status_code == 200

    # Second concurrent attempt reuses existing student & session without error
    r2 = client.post("/api/auth/coaching-candidate-onboard", json=payload)
    assert r2.status_code == 200
    assert r2.json()["student_id"] == r1.json()["student_id"]
    print("✔ test_bug_007_concurrent_onboarding_safety PASSED")


def test_bug_005_candidate_name_in_token():
    """Verify BUG-005: Candidate name is safely preserved in JWT claims for live admin alerts."""
    client = TestClient(app)

    res = client.post(
        "/api/auth/coaching-candidate-onboard",
        json={
            "name": "Deepak Patel",
            "roll_no": "ROLL-DEEPAK-06",
            "coaching_name": "Target Topper Classes",
            "exam_id": "testing-2",
        },
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    claims = decode_access_token(token)
    assert claims.get("candidate_name") == "Deepak Patel"
    assert claims.get("sub") == "ROLL-DEEPAK-06"
    assert "password" not in claims
    print("✔ test_bug_005_candidate_name_in_token PASSED")


def run_all_tests():
    print("=" * 70)
    print("RUNNING EXAMGUARD AI AUDIT REMEDIATION AUTOMATED TEST SUITE")
    print("=" * 70)
    asyncio.run(setup_test_db())
    test_bug_006_role_based_access_control()
    test_bug_002_post_submission_answer_lock()
    test_bug_008_server_session_status_and_timer()
    test_bug_001_answer_persistence_and_sync()
    test_bug_003_prevent_duplicate_attempts()
    test_bug_007_concurrent_onboarding_safety()
    test_bug_005_candidate_name_in_token()
    print("=" * 70)
    print("ALL 7 AUDIT REMEDIATION REGRESSION TESTS PASSED CLEANLY! (100% SUCCESS)")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()

