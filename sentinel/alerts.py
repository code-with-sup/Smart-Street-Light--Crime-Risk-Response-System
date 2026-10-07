"""Send incident alerts by email (SMTP) or Telegram.

Credentials are read from .env only (see .env.example). A channel without credentials
is reported as "not configured" and never attempted.
"""

from __future__ import annotations

import logging
import re
import smtplib
import ssl
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage
from pathlib import Path

import requests

from .config import env

log = logging.getLogger("sentinel.alerts")

CHANNELS = ("email", "telegram")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CHAT_ID_RE = re.compile(r"^-?\d{3,20}$")


def channel_status() -> dict:
    return {
        "email": {
            "configured": bool(env("SMTP_HOST") and env("SMTP_USER") and env("SMTP_PASSWORD")),
            "sender": env("SMTP_USER"),
            "setup": "Set SMTP_HOST, SMTP_PORT, SMTP_USER and SMTP_PASSWORD in .env "
                     "(for Gmail use smtp.gmail.com, port 465 and a Google App Password).",
        },
        "telegram": {
            "configured": bool(env("TELEGRAM_BOT_TOKEN")),
            "setup": "Create a bot with @BotFather, put its token in TELEGRAM_BOT_TOKEN in .env. Each contact "
                     "must press Start on the bot once; their numeric chat ID comes from @userinfobot.",
        },
    }


def validate_address(channel: str, address: str) -> str | None:
    if channel not in CHANNELS:
        return "Channel must be email or telegram"
    if channel == "email" and not EMAIL_RE.match(address):
        return "Enter a valid email address"
    if channel == "telegram" and not CHAT_ID_RE.match(address):
        return "Telegram needs the numeric chat ID (from @userinfobot), not a phone number or @username"
    return None


def _send_email(address: str, subject: str, body: str, image: Path | None) -> None:
    host, user, password = env("SMTP_HOST"), env("SMTP_USER"), env("SMTP_PASSWORD")
    port = int(env("SMTP_PORT", "465") or 465)
    message = EmailMessage()
    message["Subject"], message["From"], message["To"] = subject, user, address
    message.set_content(body)
    if image and image.exists():
        message.add_attachment(image.read_bytes(), maintype="image", subtype="jpeg", filename=image.name)
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as smtp:
            smtp.login(user, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.starttls(context=context)
            smtp.login(user, password)
            smtp.send_message(message)


def _send_telegram(chat_id: str, subject: str, body: str, image: Path | None) -> None:
    base = f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}"
    text = f"{subject}\n\n{body}"
    if image and image.exists():
        with image.open("rb") as handle:
            response = requests.post(f"{base}/sendPhoto", data={"chat_id": chat_id, "caption": text[:1024]},
                                     files={"photo": handle}, timeout=20)
    else:
        response = requests.post(f"{base}/sendMessage", data={"chat_id": chat_id, "text": text}, timeout=20)
    if not response.ok:
        try:
            detail = response.json().get("description", response.text)
        except ValueError:
            detail = response.text
        raise RuntimeError(f"Telegram error {response.status_code}: {detail}")


class Notifier:
    def __init__(self) -> None:
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="alerts")

    def send(self, contact: dict, subject: str, body: str, image: Path | None = None) -> tuple[bool, str]:
        channel = contact["channel"]
        if not channel_status().get(channel, {}).get("configured"):
            return False, f"{channel} is not configured in .env"
        try:
            if channel == "email":
                _send_email(contact["address"], subject, body, image)
            else:
                _send_telegram(contact["address"], subject, body, image)
            return True, ""
        except Exception as error:
            # Never echo credentials back: SMTP/requests errors do not include them.
            log.warning("alert to %s via %s failed: %s", contact.get("name"), channel, error)
            return False, str(error)[:300]

    def submit(self, fn, *args):
        return self._pool.submit(fn, *args)

    def shutdown(self) -> None:
        # don't hang shutdown on a slow SMTP server; unsent alerts are reset to "pending" on next start
        self._pool.shutdown(wait=False, cancel_futures=True)
