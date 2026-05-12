import argparse
import logging
import sys
import time

import schedule

from config import POLL_INTERVAL_MINUTES, LOG_FILE
from fetcher import fetch_html
from parser import parse_appointments
from state import load_snapshot, save_snapshot
from differ import diff_snapshots
from notifier import notify_events, send_telegram


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


log = logging.getLogger("main")


def run_once(notify_on_first_run: bool = False) -> None:
    html = fetch_html()
    if html is None:
        return

    new_rows = parse_appointments(html)
    if not new_rows:
        log.warning("Parser returned 0 rows — skipping diff to avoid spurious 'removed' events")
        return

    snap = load_snapshot()
    old_rows = snap.get("rows", [])

    if not old_rows and not notify_on_first_run:
        log.info("First run — saving baseline of %d rows, no notifications", len(new_rows))
        save_snapshot(new_rows)
        return

    events = diff_snapshots(old_rows, new_rows)
    if events:
        log.info("%d change events detected", len(events))
        notify_events(events)
    else:
        log.info("No changes")

    save_snapshot(new_rows)


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description="Schengen appointment watcher")
    parser.add_argument("--once", action="store_true", help="Run a single check and exit")
    parser.add_argument("--test-telegram", action="store_true", help="Send a test Telegram message and exit")
    parser.add_argument("--notify-first-run", action="store_true",
                        help="Send notifications for every row on the first run (default: only baseline)")
    args = parser.parse_args()

    if args.test_telegram:
        ok = send_telegram("<b>✅ Schengen watcher</b>\nTelegram connection works.")
        sys.exit(0 if ok else 1)

    if args.once:
        run_once(notify_on_first_run=args.notify_first_run)
        return

    log.info("Starting scheduler — polling every %d minute(s)", POLL_INTERVAL_MINUTES)
    run_once(notify_on_first_run=args.notify_first_run)
    schedule.every(POLL_INTERVAL_MINUTES).minutes.do(run_once)

    while True:
        schedule.run_pending()
        time.sleep(15)


if __name__ == "__main__":
    main()
