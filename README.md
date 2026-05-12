# Schengen Appointment Watcher

A lightweight Python watcher that scrapes [schengenappointments.com](https://schengenappointments.com/), detects changes in appointment availability, and pushes alerts to a Telegram bot.

Built around the fact that the appointment table is rendered **directly in the static HTML**, so no headless browser is needed — `requests` + `BeautifulSoup` is enough.

---

## Table of Contents

- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [Setup](#setup)
- [How to Run](#how-to-run)
- [How to Check the Output](#how-to-check-the-output)
- [Simulating a Change](#simulating-a-change-end-to-end-test)
- [Configuration Reference](#configuration-reference)
- [Notes & Decisions](#notes--decisions)

---

## Architecture

```
[schengenappointments.com HTML]
        │
        ▼
   requests.get()              → fetcher.py
        │
        ▼
   BeautifulSoup parse         → parser.py
        │
        ▼
   compare with cached snap    → differ.py + state.py
        │
        ▼
   send change events          → notifier.py (Telegram Bot API)
        │
        ▼
   save new snapshot to disk   → state.py (snapshot.json)
```

### Tech Stack

| Component | Choice | Why |
|---|---|---|
| Fetching | `requests` | Simple, no JS needed (data is in static HTML) |
| Parsing | `BeautifulSoup4` + `lxml` | Robust HTML table scraping |
| Diffing | Pure Python dict comparison | Lightweight, no DB needed |
| State / Cache | Local JSON file | Portable, human-readable |
| Notifications | Raw `requests` to Telegram Bot API | Zero extra deps |
| Scheduling | `schedule` library | Simple in-process loop |

### Why NOT a headless browser?

The appointment table is fully rendered in the static HTML returned by a plain HTTP GET. The HTML contains a real `<table class="table-pin-cols ...">` with one `<tr>` per country and the status text (e.g. `21 May`, `Waitlist Open`) directly inside `<span class="font-bold ...">`. So `requests` + `BeautifulSoup` is:

- ~10x faster than Playwright/Selenium
- No browser binaries to install
- Easier to deploy anywhere

---

## Project Structure

```
dataExtractor/
├── config.py           # loads env vars (token, chat id, intervals, paths)
├── fetcher.py          # HTTP GET → raw HTML
├── parser.py           # BeautifulSoup → list of row dicts
├── state.py            # load/save snapshot.json atomically
├── differ.py           # compare old vs new rows → events
├── notifier.py         # format + send Telegram messages
├── main.py             # CLI + scheduler loop
├── requirements.txt    # Python deps
├── .env.example        # template for environment variables
├── .gitignore          # excludes .env, snapshot.json, logs
├── snapshot.json       # (generated) last known state
└── extractor.log       # (generated) runtime log
```

---

## How It Works

### Per-cycle flow

```
                    ┌──────────────────────────┐
                    │   main.py (scheduler)    │
                    │   every 10 minutes       │
                    └────────────┬─────────────┘
                                 │ calls run_once()
                                 ▼
   ┌────────────────────────────────────────────────────────┐
   │  1. fetcher.py                                         │
   │     requests.get("https://schengenappointments.com/")  │
   │     → returns raw HTML string                          │
   ├────────────────────────────────────────────────────────┤
   │  2. parser.py                                          │
   │     BeautifulSoup finds <table>                        │
   │     For each <tr>: extract country, status, checked    │
   │     → returns [{country, status, status_type, ...}]    │
   ├────────────────────────────────────────────────────────┤
   │  3. state.load_snapshot()                              │
   │     Reads previous run from snapshot.json              │
   │     → returns old_rows[]                               │
   ├────────────────────────────────────────────────────────┤
   │  4. differ.py                                          │
   │     Compares new_rows vs old_rows                      │
   │     → returns events[] like:                           │
   │       [{country: "Denmark", kind: "date_changed",      │
   │         old: {...}, new: {...}}]                       │
   ├────────────────────────────────────────────────────────┤
   │  5. notifier.py                                        │
   │     For each event → format HTML message               │
   │     POST to api.telegram.org/bot.../sendMessage        │
   │     → message appears in your Telegram                 │
   ├────────────────────────────────────────────────────────┤
   │  6. state.save_snapshot(new_rows)                      │
   │     Writes new_rows to snapshot.json                   │
   │     → becomes "old" for next cycle                     │
   └────────────────────────────────────────────────────────┘
```

### Data model

Each parsed row looks like:

```json
{
  "country": "Denmark 🇩🇰",
  "country_url": "https://schengenappointments.com/in/dubai/denmark/tourism",
  "status": "21 May",
  "status_type": "available",
  "last_checked": "38 minutes ago",
  "months": { "May": false, "Jun": false, "Jul": false }
}
```

`status_type` is classified into one of:
- `available` — concrete date like `21 May`, `07 Jul`
- `waitlist` — `Waitlist Open`
- `unavailable` — `No availability` / no appointments
- `unknown` — fallback for unrecognised text

### Event kinds produced by the differ

| Kind | When it fires |
|---|---|
| `new_country` | A country appears that wasn't in the previous snapshot |
| `became_available` | Status moved from non-available → an actual date |
| `became_unavailable` | Status moved from a date → no availability/waitlist |
| `date_changed` | Was available, still available, but the date changed |
| `status_changed` | Catch-all for other transitions (e.g. waitlist ↔ unavailable) |
| `removed` | A country in the old snapshot no longer appears |

### First-run behavior

On the very first run, `snapshot.json` doesn't exist. Without protection, the differ would flag **every country as `new_country`** → spam.

So [main.py](main.py) detects an empty baseline and silently saves the initial state without sending any messages. From the second run onward, only *changes* trigger notifications.

Override with `--notify-first-run` if you want a full state dump on startup.

---

## Setup

### 1. Install Python dependencies

```powershell
py -m pip install -r requirements.txt
```

### 2. Create a Telegram bot

1. Open Telegram, search for `@BotFather`
2. Send `/newbot`, follow the prompts
3. Save the token it gives you (looks like `1234567890:ABC-DEF...`)

### 3. Find your chat ID

1. Send any message to your new bot from your Telegram account
2. Open in browser: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Find `"chat":{"id":12345678,...}` — that number is your chat ID

### 4. Configure environment variables

Copy [.env.example](.env.example) to `.env` and fill in your values:

```
TELEGRAM_BOT_TOKEN=1234567890:ABC-DEF...
TELEGRAM_CHAT_ID=12345678
TARGET_URL=https://schengenappointments.com/
POLL_INTERVAL_MINUTES=10
SNAPSHOT_FILE=snapshot.json
LOG_FILE=extractor.log
```

---

## How to Run

### Test the Telegram connection

```powershell
py main.py --test-telegram
```

Sends one test message. If it lands in your Telegram, your bot/token/chat ID are correct.

### One-off run (no scheduler)

```powershell
py main.py --once
```

Fetches, parses, diffs against `snapshot.json`, sends change messages, then exits. Ideal for cron jobs or Windows Task Scheduler.

### Continuous run (default mode)

```powershell
py main.py
```

Runs forever — first check immediately, then every `POLL_INTERVAL_MINUTES` minutes. Stop with `Ctrl+C`.

### Force first-run notifications

```powershell
py main.py --once --notify-first-run
```

Sends a Telegram message for every row even when there's no prior snapshot. Useful for sanity-checking the format.

### Run as a background scheduled task on Windows

If you'd rather not keep a terminal open, schedule the `--once` form via **Task Scheduler**:

1. Open Task Scheduler → Create Basic Task
2. Trigger: Daily, repeat every 10 minutes for 1 day
3. Action: Start a Program
4. Program/script: `py`
5. Arguments: `main.py --once`
6. Start in: `c:\Users\Universal\Documents\mufaddal\dataExtractor`

---

## How to Check the Output

### 1. Console / log file

Every run prints to both the console and [extractor.log](extractor.log):

```
2026-05-12 13:14:10 INFO [parser] Parsed 19 appointment rows
2026-05-12 13:14:10 INFO [main]   First run — saving baseline of 19 rows
2026-05-12 13:24:10 INFO [differ] Diff produced 2 events
2026-05-12 13:24:11 INFO [main]   2 change events detected
```

Tail the log live in PowerShell:

```powershell
Get-Content extractor.log -Wait -Tail 20
```

### 2. The snapshot file

[snapshot.json](snapshot.json) holds the **last known state** of the site:

```json
{
  "timestamp": "2026-05-12T13:14:10+00:00",
  "rows": [
    {
      "country": "Denmark 🇩🇰",
      "status": "21 May",
      "status_type": "available",
      "last_checked": "38 minutes ago",
      "months": { "May": false, "Jun": false, "Jul": false }
    }
  ]
}
```

Open it any time to see what the watcher currently believes the world looks like.

### 3. Telegram messages

The actual user-facing output. Examples of what you'll see:

**A new appointment opened up:**
```
🟢 Appointment available
🌍 Denmark 🇩🇰
Before: Waitlist Open (checked 38 minutes ago)
Now:    21 May (checked 2 minutes ago)
Open page
```

**Date moved earlier (the most valuable signal):**
```
🔄 Date changed
🌍 Norway 🇳🇴
Before: 14 May
Now:    07 May
Open page
```

**Availability gone:**
```
🔴 No longer available
🌍 Luxembourg
Before: 07 Jul
Now:    No availability
Open page
```

Messages are **prioritized** — `became_available` events come first since those are the ones you actually care about.

---

## Simulating a Change (end-to-end test)

To verify the full pipeline works without waiting for the real site to change:

1. Run `py main.py --once` to create a baseline
2. Open `snapshot.json` and change one country's `status` from `"21 May"` to `"99 Dec"`, save
3. Run `py main.py --once` again
4. You should get a Telegram message saying the date changed back to `21 May`

This proves the full pipeline (fetch → parse → diff → Telegram → snapshot save) is working.

---

## Configuration Reference

All settings live in `.env` (see [.env.example](.env.example)).

| Variable | Default | Purpose |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | *(required)* | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | *(required)* | Numeric chat ID where messages are sent |
| `TARGET_URL` | `https://schengenappointments.com/` | Page to scrape |
| `POLL_INTERVAL_MINUTES` | `10` | How often the scheduler runs |
| `SNAPSHOT_FILE` | `snapshot.json` | Where the last-known state is stored |
| `LOG_FILE` | `extractor.log` | Runtime log path |

### CLI flags

| Flag | What it does |
|---|---|
| `--once` | Run one check and exit (otherwise: scheduler loop) |
| `--test-telegram` | Send one test message and exit (verifies credentials) |
| `--notify-first-run` | Send notifications for every row on the first run |

---

## Notes & Decisions

### Why poll every 10 minutes?

The site explicitly states data is updated "every few minutes". 10 minutes is a balance between responsiveness and being polite to their servers. You can tighten it to 5 if you want.

### Why JSON instead of SQLite for state?

You only need the *latest* snapshot for diffing, not history. A single JSON file is:
- Easier to inspect by hand
- Easier to back up / version
- Zero schema migration burden

If you later want history (e.g. "show me how Norway's availability has moved over the last month"), SQLite makes sense.

### Why HTML scraping instead of an API?

There is no documented public API. The site says: *"The data here is pulled from visa center websites as frequently as possible."* — i.e. they're scraping too. Using their HTML table as a read-only public snapshot is the practical option.

### How fragile is the parser?

Moderately. It depends on:
- A single `<table>` on the homepage
- Status text living inside `<span class="font-bold ...">`
- "checked N minutes ago" inside `<span class="badge ...">`

If the site redesigns, the parser will need adjusting. The `_classify()` function in [parser.py](parser.py) is the regex layer that translates raw text into `available`/`waitlist`/`unavailable` — most format changes only need a tweak there.

### What about rate limiting?

The Telegram Bot API allows ~30 messages/second. We send messages serially per cycle, so unless the site adds 30+ new countries between two polls, we're well within limits.

### Atomic snapshot writes

`state.save_snapshot()` writes to `snapshot.json.tmp` first, then `os.replace()`s it over the target. This means a crash mid-write can't corrupt the snapshot — you'll either have the old version or the new one, never a half-written file.
