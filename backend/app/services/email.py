"""Email delivery service for Send-to-Kindle and other device email delivery.

Uses standard SMTP (smtplib) with the settings from config. No extra
dependencies required — smtplib and email.mime are part of the stdlib.
"""

import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger("scriptorium.email")


class EmailDeliveryError(Exception):
    pass


def is_configured() -> bool:
    settings = get_settings()
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASS)


async def send_book_to_email(
    recipient: str,
    file_path: Path,
    book_title: str,
    sender_label: str = "Scriptorium",
) -> None:
    """Send a book file as an email attachment.

    For Kindle delivery: set recipient to your @kindle.com address.
    The email subject must be empty or "Convert" to trigger automatic
    conversion on Amazon's side.

    Raises EmailDeliveryError on any failure.
    """
    settings = get_settings()
    if not is_configured():
        raise EmailDeliveryError("SMTP is not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASS in .env")

    if not file_path.exists():
        raise EmailDeliveryError(f"File not found: {file_path}")

    from_addr = settings.SMTP_FROM or settings.SMTP_USER

    msg = MIMEMultipart()
    msg["From"] = f"{sender_label} <{from_addr}>"
    msg["To"] = recipient
    msg["Subject"] = "Convert"  # Kindle: triggers conversion if needed

    # Brief body (some providers strip attachment-only emails)
    msg.attach(MIMEText(f"Sent from Scriptorium: {book_title}", "plain"))

    # Attach the book file
    with open(file_path, "rb") as f:
        part = MIMEApplication(f.read(), Name=file_path.name)
    part["Content-Disposition"] = f'attachment; filename="{file_path.name}"'
    msg.attach(part)

    try:
        if settings.SMTP_TLS:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(settings.SMTP_USER, settings.SMTP_PASS)
                smtp.sendmail(from_addr, [recipient], msg.as_string())
        else:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASS)
                smtp.sendmail(from_addr, [recipient], msg.as_string())

        logger.info("Sent '%s' (%s) to %s", book_title, file_path.name, recipient)

    except smtplib.SMTPException as exc:
        logger.error("SMTP error sending to %s: %s", recipient, exc)
        raise EmailDeliveryError(f"SMTP error: {exc}") from exc
    except OSError as exc:
        logger.error("Network error sending to %s: %s", recipient, exc)
        raise EmailDeliveryError(f"Network error: {exc}") from exc
