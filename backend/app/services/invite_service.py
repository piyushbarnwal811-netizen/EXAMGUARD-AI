from __future__ import annotations

import hashlib
import secrets
from datetime import datetime

from app.config import get_settings
from app.services.email_service import send_email

def create_invite_token() -> str:
    return secrets.token_urlsafe(32)

def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def build_exam_invite_link(token: str) -> str:
    settings = get_settings()
    # Prefer FRONTEND_URL, fallback to FRONTEND_EXAM_URL
    base = getattr(settings, "FRONTEND_URL", "") or getattr(settings, "FRONTEND_EXAM_URL", "") or ""
    base = str(base).strip().rstrip("/")
    if base.endswith("/exam"):
        base = base[:-5]
    if base.endswith("/src/pages/student-exam.html"):
        base = base.replace("/src/pages/student-exam.html", "")
    if base.endswith("/src/pages/exam.html"):
        base = base.replace("/src/pages/exam.html", "")
    if not base:
        base = "https://examguard-ai.vercel.app"
    # Clean URL - Vercel rewrite /exam -> /src/pages/exam.html
    return f"{base}/exam?token={token}"

def _format_expiry(expires_at: datetime) -> str:
    return expires_at.astimezone().strftime("%Y-%m-%d %H:%M %Z")

def build_invite_email_body(
    student_name: str,
    invite_link: str,
    pin: str,
    expires_at: datetime,
) -> str:
    return (
        f"Hello {student_name},\n\n"
        f"Your ExamGuard AI Secure Exam Link (Safe Exam Browser Required):\n{invite_link}\n\n"
        f"Your PIN: {pin}\n\n"
        f"This link expires on {_format_expiry(expires_at)} and can be used once.\n"
        "Steps:\n"
        "1. Click the link above\n"
        "2. If Safe Exam Browser is installed, exam will open in SEB\n"
        "3. If not installed, you will see a download page - download SEB config + Safe Browser\n"
        "4. After install, open the .seb file - exam will auto-launch\n"
        "5. Enter your PIN to unlock\n\n"
        "If you were not expecting this invitation, please contact your exam admin.\n"
    )

def send_exam_invite_email(
    to_email: str,
    student_name: str,
    invite_link: str,
    pin: str,
    expires_at: datetime,
) -> None:
    send_email(
        to_email=to_email,
        subject="Your ExamGuard AI exam access link",
        body=build_invite_email_body(student_name, invite_link, pin, expires_at),
    )
