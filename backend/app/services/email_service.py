import smtplib
import ssl
import logging
import time
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
import re
from typing import Iterable

from app.config import get_settings

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)

logger = logging.getLogger(__name__)


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
    if not clean_address:
        clean_address = smtp_user
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


def send_email(
    to_email: str,
    subject: str,
    body: str,
    html_body: str | None = None,
) -> None:
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
    if html_body:
        message.add_alternative(html_body, subtype="html")

    # Determine primary and fallback connection strategies
    primary_ssl = settings.SMTP_USE_SSL or settings.SMTP_PORT == 465
    primary_port = settings.SMTP_PORT
    fallback_ssl = not primary_ssl
    fallback_port = 465 if primary_port == 587 else 587

    strategies = [
        ("primary", primary_ssl, primary_port),
        ("fallback", fallback_ssl, fallback_port),
    ]

    context = ssl.create_default_context()
    max_attempts = 2  # per strategy
    last_error: smtplib.SMTPException | OSError | None = None

    for label, use_ssl, port in strategies:
        for attempt in range(1, max_attempts + 1):
            try:
                if use_ssl:
                    smtp = smtplib.SMTP_SSL(
                        settings.SMTP_HOST,
                        port,
                        timeout=settings.SMTP_TIMEOUT_SECONDS,
                        context=context,
                    )
                else:
                    smtp = smtplib.SMTP(
                        settings.SMTP_HOST,
                        port,
                        timeout=settings.SMTP_TIMEOUT_SECONDS,
                    )

                with smtp as server:
                    server.ehlo()
                    if not use_ssl:
                        server.starttls(context=context)
                        server.ehlo()
                    server.login(smtp_user, smtp_password)
                    server.send_message(message)
                logger.info("Email sent to %s via %s (port %s, ssl=%s)", to_email, label, port, use_ssl)
                return  # success
            except smtplib.SMTPAuthenticationError as exc:
                # auth errors are not transient, abort all strategies
                raise EmailDeliveryError(
                    "SMTP authentication failed. Check SMTP_USER and SMTP_PASSWORD; "
                    "for Gmail, use an app password."
                ) from exc
            except (smtplib.SMTPException, OSError) as exc:
                last_error = exc
                if attempt == max_attempts:
                    logger.warning("Strategy %s (port %s, ssl=%s) attempt %s failed: %s", label, port, use_ssl, attempt, exc)
                    break  # try next strategy
                # transient network error – wait a bit and retry
                time.sleep(1.5 * attempt)

    raise EmailDeliveryError(
        f"SMTP delivery failed for {to_email} after trying primary and fallback "
        f"strategies. Last error: {last_error or 'unknown SMTP error'}"
    ) from last_error


def send_bulk_emails(recipients: Iterable[str], subject: str, body: str) -> int:
    sent = 0
    for recipient in recipients:
        try:
            send_email(recipient, subject, body)
            sent += 1
        except EmailDeliveryError as exc:
            logger.error("Failed to send email to %s: %s", recipient, exc)
            # continue with next recipient
    return sent
