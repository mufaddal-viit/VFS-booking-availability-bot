import logging
import html
import time
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, REQUEST_TIMEOUT

log = logging.getLogger(__name__)

TG_API = "https://api.telegram.org/bot{token}/sendMessage"

_RETRY_DELAYS = (2, 5)  # seconds to wait before 2nd and 3rd attempts


def send_telegram(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram credentials missing — skipping send")
        return False

    url = TG_API.format(token=TELEGRAM_BOT_TOKEN)
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    attempt = 0
    for delay in [0] + list(_RETRY_DELAYS):
        if delay:
            time.sleep(delay)
        attempt += 1
        try:
            r = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                return True
            log.warning("Telegram API attempt %d returned %s: %s", attempt, r.status_code, r.text[:200])
        except requests.RequestException as e:
            log.warning("Telegram send attempt %d failed: %s", attempt, e)

    log.error("Telegram send failed after %d attempts", attempt)
    return False


def notify_events(events: list[dict]) -> None:
    if not events:
        return

    log.info("All events: %s", [e["kind"] for e in events])

    # Notify on:
    #   - became_available: slot opened up
    #   - date_changed: available slot moved to a different date
    #   - new_country on first run only if already available
    # NOT notified: became_unavailable, status_changed, removed
    # last_checked changes never reach here — they are excluded in differ.py
    def is_notifiable(e: dict) -> bool:
        if e["kind"] in ("became_available", "date_changed"):
            return True
        if e["kind"] == "new_country":
            return (e.get("new") or {}).get("status_type") == "available"
        return False

    relevant = [e for e in events if is_notifiable(e)]
    log.info("Notifiable events (open/changed slots): %d", len(relevant))

    for ev in relevant:
        new_row = ev.get("new")
        if not new_row:
            continue
        country = new_row.get("country", "?")
        status = new_row.get("status", "?")
        url = new_row.get("country_url", "")
        city = (new_row.get("city") or "").replace("-", " ").title()
        visa = (new_row.get("visa_type") or "").title()
        kind = ev["kind"]

        header = "Appointment Available" if kind in ("became_available", "new_country") else "Date Changed"

        parts = [
            f"<b>{html.escape(header)}</b>",
            f"<b>Destination country:</b> {html.escape(country)}",
            f"<b>Source destination:</b> {html.escape(city)}",
            f"<b>Booking date:</b> {html.escape(status)}",
            f"<b>Visa type:</b> {html.escape(visa)}",
        ]
        if kind == "date_changed":
            old_status = (ev.get("old") or {}).get("status", "?")
            parts.insert(2, f"<b>Previous date:</b> {html.escape(old_status)}")
        if url:
            parts.append(f'<a href="{html.escape(url)}">Click here to book now</a>')
        text = "\n".join(parts)

        country_clean = country.encode("ascii", "ignore").decode("ascii").strip()
        log.info("Notifying: %s | %s | %s | %s", country_clean, kind, status, ev.get("source_key"))
        send_telegram(text)
