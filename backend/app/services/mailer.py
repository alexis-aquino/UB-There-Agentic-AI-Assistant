"""Renders and (optionally) sends escalation emails.

Default mode is dry_run: the message is composed and stored so it can be reviewed in the
admin dashboard, but nothing leaves the machine. Live sending has to be turned on
deliberately, because the recipients are real university offices.
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from app.config import get_settings
from app.db.models import Escalation


@dataclass
class DeliveryResult:
    delivered: bool
    mode: str
    error: str = ""


def render(escalation: Escalation, department_name: str, department_email: str) -> str:
    student = escalation.student_email or "(not provided)"
    name = escalation.student_name or "A student"

    body = f"""To: {department_name} <{department_email}>
Subject: [UB There] Student inquiry {escalation.reference_code}

{name} asked a question that UB There could not answer from the official documents.

Reference code : {escalation.reference_code}
Student contact: {student}
Confidence     : {escalation.confidence:.2f}
Routing        : {escalation.routing_reason}

--- Question -------------------------------------------------
{escalation.question}

--- What the assistant could find ----------------------------
{escalation.partial_answer or "(nothing relevant in the indexed documents)"}

---------------------------------------------------------------
Reply to the student directly. They can check the status of this
inquiry using the reference code above.

Sent automatically by UB There.
"""
    return body.strip()


def deliver(escalation: Escalation, department_email: str) -> DeliveryResult:
    settings = get_settings()

    if settings.mail_mode != "live":
        return DeliveryResult(delivered=False, mode="dry_run")

    if not settings.smtp_host:
        return DeliveryResult(
            delivered=False,
            mode="live",
            error="MAIL_MODE is live but SMTP_HOST is not configured.",
        )

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = department_email
    message["Subject"] = f"[UB There] Student inquiry {escalation.reference_code}"
    if escalation.student_email:
        message["Reply-To"] = escalation.student_email
    message.set_content(escalation.rendered_email)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
        return DeliveryResult(delivered=True, mode="live")
    except Exception as exc:
        return DeliveryResult(delivered=False, mode="live", error=str(exc))
