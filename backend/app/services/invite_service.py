from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.config import get_settings
from app.services.email_service import send_email


def create_invite_token() -> str:
    return secrets.token_urlsafe(32)


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def build_exam_invite_link(token: str) -> str:
    settings = get_settings()
    parts = urlsplit(settings.FRONTEND_EXAM_URL)
    # Ensure the path points to the exam page
    path = parts.path.rstrip('/')
    if not path.endswith('/exam'):
        path = f"{path}/exam" if path else "/exam"
    query = parse_qsl(parts.query, keep_blank_values=True)
    query.append(("invite", token))
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            path,
            urlencode(query),
            parts.fragment,
        )
    )


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
        "You have been invited to take your ExamGuard AI exam.\n\n"
        "Open this secure access link to begin:\n"
        f"{invite_link}\n\n"
        "Use this PIN when the exam page asks for it:\n"
        f"{pin}\n\n"
        f"This link expires on {_format_expiry(expires_at)} and can be used once.\n"
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
