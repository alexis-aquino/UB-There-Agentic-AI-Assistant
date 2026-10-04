"""Outgoing email from the app's own address.

MAIL_MODE=log (the default) writes each message to backend/outbox/ as an .eml file you can
open in any mail program, so the whole flow works before a mailbox exists. MAIL_MODE=smtp
sends it for real — with Gmail, through smtp.gmail.com and an app password.
"""

from __future__ import annotations

import logging
import re
import smtplib
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app.config import get_settings

logger = logging.getLogger(__name__)


class MailError(RuntimeError):
    pass


def send(to: str, subject: str, body: str) -> str:
    """Send a plain-text email. Returns where it went (a file path in log mode)."""
    settings = get_settings()

    message = EmailMessage()
    sender = settings.smtp_user or "ub-there@localhost"
    message["From"] = formataddr((settings.mail_from_name, sender))
    message["To"] = to
    message["Subject"] = subject
    message["Message-ID"] = make_msgid(domain=sender.split("@")[-1])
    message.set_content(body)

    if settings.mail_mode == "log":
        outbox = settings.mail_outbox_dir
        outbox.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", subject.lower())[:50].strip("-")
        path = outbox / f"{datetime.now():%Y%m%d-%H%M%S-%f}-{slug}.eml"
        path.write_bytes(bytes(message))
        logger.info("Email logged (MAIL_MODE=log): %s -> %s", to, path)
        return str(path)

    if not settings.smtp_user or not settings.smtp_password:
        raise MailError("Email is not set up: SMTP_USER and SMTP_PASSWORD are missing in backend/.env.")
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        logger.exception("Sending email failed")
        raise MailError(f"Could not send the email: {exc}") from exc
    return to
