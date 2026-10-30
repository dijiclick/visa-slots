"""Telegram alerts. TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID (comma-separated for several chats)."""
import html
import logging
import os

import requests

log = logging.getLogger(__name__)


def send(text: str, silent: bool = False) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chats = [c.strip() for c in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if c.strip()]
    if not token or not chats:
        log.warning("telegram not configured; would send: %s", text)
        return False
    ok = True
    for chat in chats:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True,
                      "disable_notification": silent},
                timeout=20,
            )
            ok &= r.ok
            if not r.ok:
                log.error("telegram %s: %s", r.status_code, r.text[:200])
        except requests.RequestException as e:
            log.error("telegram: %s", e)
            ok = False
    return ok


def esc(s: str) -> str:
    return html.escape(s or "", quote=False)
