"""Sender-agnostic account-recovery email (SEC-013).

`ConsoleEmailSender` is the default so local development works with zero
configuration — it logs the message instead of sending it. `SmtpEmailSender`
activates only when `smtp_host` is configured; the factory picks between them.
"""

import logging
from email.message import EmailMessage
from smtplib import SMTP, SMTPException
from typing import Protocol

from app.core.database import settings

logger = logging.getLogger("chess-engine-api.email")


class EmailSender(Protocol):
    """Deliver a plain-text email. Implementations must never raise to callers."""

    def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailSender:
    """Development sender: writes the message to the log, sends nothing."""

    def send(self, to: str, subject: str, body: str) -> None:
        logger.info("EMAIL (console sender) to=%s subject=%r\n%s", to, subject, body)


class SmtpEmailSender:
    """Submits through a configured SMTP relay; failures are logged, not raised."""

    def send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = settings.smtp_from or settings.smtp_username
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        try:
            with SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
                server.starttls()
                if settings.smtp_username:
                    server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(message)
        except (SMTPException, OSError) as exc:  # pragma: no cover - network path
            # A failed send must not 500 the recovery endpoint: the uniform
            # response keeps the flow non-enumerable, and the token simply goes
            # undelivered (the user can request it again).
            logger.warning("SMTP send failed to=%s: %s", to, exc)


_sender: EmailSender | None = None


def build_email_sender() -> EmailSender:
    """Pick a sender from config: SMTP when `smtp_host` is set, else console."""
    if settings.smtp_host.strip():
        return SmtpEmailSender()
    return ConsoleEmailSender()


def get_email_sender() -> EmailSender:
    """Process-wide cached sender (cheap to construct; tests reset via factory)."""
    global _sender
    if _sender is None:
        _sender = build_email_sender()
    return _sender
