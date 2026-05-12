import argparse
import logging
import sys
import time

import schedule

from config import POLL_INTERVAL_MINUTES, LOG_FILE, SOURCES
from fetcher import fetch_html
from parser import parse_appointments
from state import load_snapshot, save_snapshot
from differ import diff_snapshots
from notifier import notify_events, send_telegram
from debug import dump_html, dump_parsed


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


def collect_all_rows(write_debug: bool = False) -> list[dict]:
    """Fetch & parse every configured source. Returns merged row list.

    When write_debug=True, raw HTML and parsed dump are written to disk.
    """
    all_rows: list[dict] = []
    parsed_by_source: dict[str, list[dict]] = {}

    for src in SOURCES:
        log.info("Fetching %s", src["url"])
        html = fetch_html(src["url"])
        if html is None:
            log.error("Skipping %s — fetch failed", src["key"])
            continue

        if write_debug:
            dump_html(html, src["key"])

        rows = parse_appointments(html, source=src)
        parsed_by_source[src["key"]] = rows
        all_rows.extend(rows)

    if write_debug:
        dump_parsed(parsed_by_source)

    return all_rows


def run_once(notify_on_first_run: bool = True, write_debug: bool = False) -> None:
    new_rows = collect_all_rows(write_debug=write_debug)
    if not new_rows:
        log.warning("No rows parsed from any source — skipping diff")
        return

    snap = load_snapshot()
    old_rows = snap.get("rows", [])

    if not old_rows:
        if notify_on_first_run:
            log.info("First run — notifying for all currently available slots (%d rows)", len(new_rows))
            events = diff_snapshots(old_rows, new_rows)
            notify_events(events)
        else:
            log.info("First run — saving baseline of %d rows silently", len(new_rows))
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
    parser.add_argument("--silent-first-run", action="store_true",
                        help="Suppress notifications on the very first run (just save baseline)")
    parser.add_argument("--debug-dump", action="store_true",
                        help="Save raw HTML and parsed-data dumps to disk for inspection")
    args = parser.parse_args()

    if args.test_telegram:
        ok = send_telegram("<b>✅ Schengen watcher</b>\nTelegram connection works.")
        sys.exit(0 if ok else 1)

    notify_first = not args.silent_first_run

    if args.once:
        run_once(notify_on_first_run=notify_first, write_debug=args.debug_dump)
        return

    log.info("Starting scheduler — polling every %d minute(s)", POLL_INTERVAL_MINUTES)
    run_once(notify_on_first_run=notify_first, write_debug=args.debug_dump)
    schedule.every(POLL_INTERVAL_MINUTES).minutes.do(
        run_once, notify_on_first_run=False, write_debug=args.debug_dump
    )

    while True:
        schedule.run_pending()
        time.sleep(15)


if __name__ == "__main__":
    main()
