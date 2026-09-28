"""Contact form: a visitor's message, delivered by e-mail to the site owner.

The recipient address comes from configuration (``CONTACT_EMAIL`` in ``.env``)
and never reaches the page. Abuse guards: a honeypot field bots fill in, a
per-IP rate limit, length limits, and address validation (the visitor's e-mail
goes into ``Reply-To``, so it must not carry header injection).
"""
import re
import smtplib
import ssl
import threading
import time
from collections import defaultdict, deque
from email.message import EmailMessage

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from config.settings import settings
from monitoring import metrics
from utils.logger import get_logger

router = APIRouter(tags=["contact"])
logger = get_logger(__name__)

_EMAIL = re.compile(r"^[^@\s<>,;\"']{1,64}@[^@\s<>,;\"']{1,255}\.[A-Za-z]{2,63}$")
_recent: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(max_length=200)
    message: str = Field(min_length=10, max_length=5000)
    website: str = ""  # honeypot: hidden from people
    lang: str = Field(default="", max_length=16)

    @field_validator("name")
    @classmethod
    def one_line(cls, v: str) -> str:
        v = v.strip()
        if not v or "\r" in v or "\n" in v:
            raise ValueError("invalid name")
        return v

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        v = v.strip()
        if not _EMAIL.match(v):
            raise ValueError("invalid email")
        return v


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "?"


def _allowed(ip: str) -> bool:
    """Sliding-window limit per IP. ponytail: in memory, per process; a shared
    store (Redis) if the app ever runs on several workers."""
    now = time.monotonic()
    with _lock:
        hits = _recent[ip]
        while hits and now - hits[0] > settings.contact_rate_window_s:
            hits.popleft()
        if len(hits) >= settings.contact_rate_limit:
            return False
        hits.append(now)
        return True


def _send(msg: EmailMessage) -> None:
    timeout = 20
    if settings.smtp_security == "ssl":
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=timeout,
                                  context=ssl.create_default_context())
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout)
    with server:
        if settings.smtp_security == "starttls":
            server.starttls(context=ssl.create_default_context())
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)


@router.post("/contact")
def contact(body: ContactIn, request: Request):
    if not (settings.contact_email and settings.smtp_host):
        metrics.CONTACT_COUNT.labels(result="unconfigured").inc()
        raise HTTPException(503, "contact form not configured")
    if body.website:  # a bot filled the invisible field: pretend it worked
        metrics.CONTACT_COUNT.labels(result="honeypot").inc()
        return {"ok": True}
    ip = _client_ip(request)
    if not _allowed(ip):
        metrics.CONTACT_COUNT.labels(result="rate_limited").inc()
        raise HTTPException(429, "too many messages")

    msg = EmailMessage()
    msg["Subject"] = f"INSTRINDER — message from {body.name}"
    msg["From"] = settings.contact_from or settings.smtp_user or settings.contact_email
    msg["To"] = settings.contact_email
    msg["Reply-To"] = body.email
    msg.set_content(
        f"Name: {body.name}\nEmail: {body.email}\nPage language: {body.lang or '-'}\n"
        f"IP: {ip}\n\n{body.message}\n"
    )
    try:
        _send(msg)
    except (OSError, smtplib.SMTPException) as exc:
        logger.error("contact mail not sent: %s", exc)
        metrics.CONTACT_COUNT.labels(result="smtp_error").inc()
        raise HTTPException(502, "could not send the message") from exc
    metrics.CONTACT_COUNT.labels(result="sent").inc()
    return {"ok": True}
