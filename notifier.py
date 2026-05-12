import logging
import html
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, REQUEST_TIMEOUT

log = logging.getLogger(__name__)

TG_API = "https://api.telegram.org/bot{token}/sendMessage"

KIND_HEADER = {
    "new_country": "🆕 New country listed",
    "became_available": "🟢 Appointment available",
    "became_unavailable": "🔴 No longer available",
    "date_changed": "🔄 Date changed",
    "status_changed": "ℹ️ Status changed",
    "removed": "❌ Country removed",
}


def _row_line(row: dict | None) -> str:
    if not row:
        return "—"
    status = html.escape(row.get("status") or "—")
    checked = html.escape(row.get("last_checked") or "")
    suffix = f" <i>(checked {checked})</i>" if checked else ""
    return f"{status}{suffix}"


def format_event(event: dict) -> str:
    kind = event["kind"]
    country = html.escape(event["country"])
    header = KIND_HEADER.get(kind, kind)
    new = event.get("new")
    old = event.get("old")
    url = (new or old or {}).get("country_url")

    lines = [f"<b>{header}</b>", f"🌍 <b>{country}</b>"]

    if kind == "new_country":
        lines.append(f"Status: {_row_line(new)}")
    elif kind in ("became_available", "became_unavailable", "date_changed", "status_changed"):
        lines.append(f"Before: {_row_line(old)}")
        lines.append(f"Now:    {_row_line(new)}")
    elif kind == "removed":
        lines.append(f"Was: {_row_line(old)}")

    if url:
        lines.append(f'<a href="{html.escape(url)}">Open page</a>')
    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram credentials missing (message queued locally)")
        return False
    try:
        r = requests.post(
            TG_API.format(token=TELEGRAM_BOT_TOKEN),
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code != 200:
            log.error("Telegram API %s: %s", r.status_code, r.text)
            return False
        return True
    except requests.RequestException as e:
        log.error("Telegram send failed: %s", e)
        return False


def notify_events(events: list[dict]) -> None:
    if not events:
        return

    log.info("All events: %s", [e["kind"] for e in events])

    # Only notify on available slot changes
    relevant = [e for e in events if e["kind"] in ("became_available", "date_changed")]
    log.info("Relevant events (became_available/date_changed): %d", len(relevant))

    for ev in relevant:
        new_row = ev.get("new")
        if not new_row:
            continue
        country = new_row.get("country", "?")
        status = new_row.get("status", "?")
        url = new_row.get("country_url", "")

        text = f"🟢 {country}\n📅 {status}"
        if url:
            text += f'\n<a href="{url}">Book now</a>'

        # Log without emojis (for Windows console compatibility)
        country_clean = "".join(c for c in country if ord(c) < 0x1F600 or ord(c) > 0x1F64F)
        log.info("Sent: %s | %s", country_clean.strip(), status)
        send_telegram(text)
