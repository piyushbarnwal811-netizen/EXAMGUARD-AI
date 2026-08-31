import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
import re
from typing import Iterable

from app.config import get_settings

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


class EmailConfigurationError(RuntimeError):
    pass


class EmailDeliveryError(RuntimeError):
    pass


def _clean_email_address(value: str) -> str:
    stripped = (value or "").strip()
    match = EMAIL_RE.search(stripped)
    if match:
        return match.group(0)
    parsed = parseaddr(stripped)[1]
    return parsed or stripped


def _clean_smtp_password(value: str) -> str:
    password = (value or "").strip()
    if "#" in password:
        password = password.split("#", 1)[0].strip()
    if " " in password:
        return password.replace(" ", "")
    return password


def _clean_from_header(email_from: str, fallback_email: str) -> str:
    name, address = parseaddr((email_from or "").strip())
    clean_address = _clean_email_address(address or email_from or fallback_email)
    return formataddr((name, clean_address)) if name else clean_address


def _smtp_from_header(email_from: str, smtp_user: str, smtp_host: str) -> str:
    name, address = parseaddr((email_from or "").strip())
    clean_address = _clean_email_address(address or email_from or smtp_user)
    if "gmail" in (smtp_host or "").lower() and clean_address.lower() != smtp_user.lower():
        clean_address = smtp_user
    return formataddr((name, clean_address)) if name else clean_address


def _require_email_settings():
    settings = get_settings()
    missing: list[str] = []
    if not settings.SMTP_HOST:
        missing.append("SMTP_HOST")
    if not settings.SMTP_PORT:
        missing.append("SMTP_PORT")
    if not settings.SMTP_USER:
        missing.append("SMTP_USER")
    if not settings.SMTP_PASSWORD:
        missing.append("SMTP_PASSWORD")

    if missing:
        raise EmailConfigurationError(
            f"SMTP is not configured. Missing: {', '.join(missing)}."
        )

    return settings


def validate_email_settings() -> None:
    settings = _require_email_settings()
    if not _clean_email_address(settings.SMTP_USER):
        raise EmailConfigurationError("SMTP_USER must contain a valid email address.")
    if not _clean_smtp_password(settings.SMTP_PASSWORD):
        raise EmailConfigurationError("SMTP_PASSWORD must not be empty.")


import time

def send_email(to_email: str, subject: str, body: str) -> None:
    settings = _require_email_settings()
    smtp_user = _clean_email_address(settings.SMTP_USER)
    smtp_password = _clean_smtp_password(settings.SMTP_PASSWORD)

    message = EmailMessage()
    message["From"] = _smtp_from_header(
        settings.EMAIL_FROM,
        smtp_user,
        settings.SMTP_HOST,
    )
    message["To"] = _clean_email_address(to_email)
    message["Subject"] = subject
    message.set_content(body)

    use_ssl = settings.SMTP_USE_SSL or settings.SMTP_PORT == 465
    context = ssl.create_default_context()

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            if use_ssl:
                smtp = smtplib.SMTP_SSL(
                    settings.SMTP_HOST,
                    settings.SMTP_PORT,
                    timeout=settings.SMTP_TIMEOUT_SECONDS,
                    context=context,
                )
            else:
                smtp = smtplib.SMTP(
                    settings.SMTP_HOST,
                    settings.SMTP_PORT,
                    timeout=settings.SMTP_TIMEOUT_SECONDS,
                )

            with smtp as server:
                server.ehlo()
                if not use_ssl and settings.SMTP_STARTTLS:
                    server.starttls(context=context)
                    server.ehlo()
                server.login(smtp_user, smtp_password)
                server.send_message(message)
            return  # success
        except smtplib.SMTPAuthenticationError as exc:
            # auth errors are not transient
            raise EmailDeliveryError(
                "SMTP authentication failed. Check SMTP_USER and SMTP_PASSWORD; "
                "for Gmail, use an app password."
            ) from exc
        except (smtplib.SMTPException, OSError) as exc:
            if attempt == max_attempts:
                raise EmailDeliveryError(f"SMTP delivery failed after {max_attempts} attempts: {exc}") from exc
            # transient network error – wait a bit and retry
            time.sleep(1.5 * attempt)


def send_bulk_emails(recipients: Iterable[str], subject: str, body: str) -> int:
    sent = 0
    for recipient in recipients:
        send_email(recipient, subject, body)
        sent += 1
    return sent
