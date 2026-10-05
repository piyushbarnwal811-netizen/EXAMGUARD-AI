from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from html import escape

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
    return f"{base}/exam?token={token}"

def _format_expiry(expires_at: datetime) -> str:
    return expires_at.astimezone().strftime("%Y-%m-%d %H:%M %Z")

def build_invite_email_body(
    student_name: str,
    invite_link: str,
    expires_at: datetime,
) -> str:
    return (
        f"Hello {student_name},\n\n"
        f"Open this one-time exam link in Safe Exam Browser (SEB) to start your exam:\n{invite_link}\n\n"
        f"This link expires on {_format_expiry(expires_at)} and can be used once.\n\n"
        "Important: before the exam starts, the browser will check whether Safe Exam Browser is installed.\n"
        "If it is not installed, download the Safe Browser and the .seb configuration file, then open the .seb file to launch the exam.\n\n"
        "Steps:\n"
        "1. Click the link above\n"
        "2. Let the SEB check run before exam start\n"
        "3. If SEB is missing, download the SEB config and installer\n"
        "4. Open the .seb file to start the exam automatically\n"
        "5. The exam will start automatically after the one-time link is verified\n\n"
        "If you were not expecting this invitation, please contact your exam admin.\n"
    )

def build_invite_email_html(
    student_name: str,
    invite_link: str,
    expires_at: datetime,
) -> str:
    settings = get_settings()
    app_name = escape(settings.APP_NAME)
    safe_name = escape(student_name)
    safe_link = escape(invite_link, quote=True)
    safe_expiry = escape(_format_expiry(expires_at))
    return (
        '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;'
        'color:#202733;line-height:1.6">'
        f'<h1 style="color:#176b5b">{app_name}</h1>'
        f'<p>Hello {safe_name},</p>'
        '<p>Your secure exam invitation is ready. Open the link from Safe Exam Browser:</p>'
        f'<p><a href="{safe_link}" style="display:inline-block;padding:12px 18px;'
        'background:#176b5b;color:#fff;text-decoration:none;border-radius:4px">Open exam</a></p>'
        f'<p>If the button does not work, use this link:<br><a href="{safe_link}">{safe_link}</a></p>'
        f'<p><strong>This link can be used once.</strong><br>'
        f'<strong>Link expires:</strong> {safe_expiry}</p>'
        '<p>Before the exam starts, SEB and system checks must pass. If SEB is missing, '
        'download the installer and exam configuration shown on the exam page, then open the .seb file.</p>'
        '<p>Do not forward this email. Contact your exam administrator if you did not expect it.</p>'
        '</div>'
    )

def send_exam_invite_email(
    to_email: str,
    student_name: str,
    invite_link: str,
    expires_at: datetime,
) -> None:
    send_email(
        to_email=to_email,
        subject="Your ExamGuard AI exam access link",
        body=build_invite_email_body(student_name, invite_link, expires_at),
        html_body=build_invite_email_html(student_name, invite_link, expires_at),
    )
