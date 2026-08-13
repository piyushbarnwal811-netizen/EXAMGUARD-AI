import smtplib
from email.message import EmailMessage
from typing import Iterable

from app.config import get_settings

settings = get_settings()


def send_email(to_email: str, subject: str, body: str) -> None:
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        raise RuntimeError("SMTP credentials are not configured.")

    message = EmailMessage()
    message["From"] = settings.EMAIL_FROM or settings.SMTP_USER
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(message)


def send_bulk_emails(recipients: Iterable[str], subject: str, body: str) -> int:
    sent = 0
    for recipient in recipients:
        send_email(recipient, subject, body)
        sent += 1
    return sent
