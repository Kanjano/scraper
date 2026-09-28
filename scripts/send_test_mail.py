"""Check the contact-form mail settings by sending one test message.

Uses exactly the configuration of POST /contact (SMTP_* and CONTACT_EMAIL from
.env), so a success here means the form will deliver too.

Usage:  python -m scripts.send_test_mail
"""
import sys
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.routes.contact import _send  # noqa: E402
from config.settings import settings  # noqa: E402


def main() -> int:
    missing = [k for k in ("contact_email", "smtp_host") if not getattr(settings, k)]
    if missing:
        print("Not configured in .env:", ", ".join(k.upper() for k in missing))
        return 2
    msg = EmailMessage()
    msg["Subject"] = "INSTRINDER — test message"
    msg["From"] = settings.contact_from or settings.smtp_user or settings.contact_email
    msg["To"] = settings.contact_email
    msg.set_content("If you can read this, the INSTRINDER contact form can deliver mail.\n")
    print(f"Sending through {settings.smtp_host}:{settings.smtp_port} "
          f"({settings.smtp_security}) as {msg['From']} …")
    try:
        _send(msg)
    except Exception as exc:  # noqa: BLE001 — report any failure plainly
        print(f"FAILED: {type(exc).__name__}: {exc}")
        if "535" in str(exc) or "Username and Password" in str(exc):
            print("Gmail: SMTP_PASSWORD must be an *app password*, not the account password.")
        return 1
    print("Sent. Check the inbox of CONTACT_EMAIL.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
