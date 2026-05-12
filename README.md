# Schengen Appointment Watcher

A lightweight Python watcher that scrapes [schengenappointments.com](https://schengenappointments.com/) for **Abu Dhabi and Dubai** (tourism + business visa types), detects changes in appointment availability, and pushes alerts to a Telegram bot.

Each Telegram alert links directly to the VFS Global booking page for that country, so the recipient can act in one tap.

Built around the fact that the appointment table is rendered **directly in the static HTML**, so no headless browser is needed — `requests` + `BeautifulSoup` is enough.

---

## Table of Contents

- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [What Triggers a Telegram Message](#what-triggers-a-telegram-message)
- [Setup](#setup)
- [How to Run](#how-to-run)
- [How to Check the Output](#how-to-check-the-output)
- [Debug Dumps](#debug-dumps)
- [Snapshot Mechanics](#snapshot-mechanics)
- [Simulating a Change](#simulating-a-change-end-to-end-test)
- [Configuration Reference](#configuration-reference)
- [Notes & Decisions](#notes--decisions)

---

## Architecture

```
                       ┌──────────────────────────────────┐
  4 source URLs ───►   │  fetcher.py — requests.get()     │
  (city × visa_type)   │                                  │
                       │  parser.py — BeautifulSoup       │
                       │    • extract country, status     │
                       │    • map country → VFS URL       │
                       │    • tag with source             │
                       └────────────┬─────────────────────┘
                                    │
                                    ▼  list of 69 row dicts
                       ┌──────────────────────────────────┐
                       │  differ.py                       │
                       │    • compare with snapshot.json  │
                       │    • ignore `last_checked`       │
                       │    • produce change events       │
                       └────────────┬─────────────────────┘
                                    │
                                    ▼  events[]
                       ┌──────────────────────────────────┐
                       │  notifier.py                     │
                       │    • filter: only available-slot │
                       │      events (became_available,   │
                       │      date_changed)               │
                       │    • POST to Telegram Bot API    │
                       └────────────┬─────────────────────┘
                                    │
                                    ▼
                       ┌──────────────────────────────────┐
                       │  state.py                        │
                       │    save_snapshot(new_rows)       │
                       │    → snapshot.json (atomic)      │
                       └──────────────────────────────────┘
```

### Sources

4 URLs are scraped every cycle, defined in [config.py](config.py):

| key | URL |
|---|---|
| `abu-dhabi/tourism` | `https://schengenappointments.com/in/abu-dhabi/tourism` |
| `abu-dhabi/business` | `https://schengenappointments.com/in/abu-dhabi/business` |
| `dubai/tourism` | `https://schengenappointments.com/in/dubai/tourism` |
| `dubai/business` | `https://schengenappointments.com/in/dubai/business` |

Each parsed row is tagged with `source_key`, `city`, `visa_type`, and gets a stable id `{source_key}::{country}` so countries from different sources never collide.

### Tech Stack

| Component | Choice | Why |
|---|---|---|
| Fetching | `requests` | Simple, no JS needed (data is in static HTML) |
| Parsing | `BeautifulSoup4` + `lxml` | Robust HTML table scraping |
| Diffing | Pure Python dict comparison | Lightweight, no DB needed |
| State / Cache | Local JSON file | Portable, human-readable |
| Notifications | Raw `requests` to Telegram Bot API | Zero extra deps |
| Scheduling | `schedule` library | Simple in-process loop |

---

## Project Structure

```
dataExtractor/
├── config.py           # env vars + 4-source URL builder
├── countries.py        # country name → VFS Global ISO-3 code mapping
├── fetcher.py          # HTTP GET → raw HTML
├── parser.py           # BeautifulSoup → list of row dicts (with VFS URLs)
├── state.py            # load/save snapshot.json atomically
├── differ.py           # compare old vs new rows → events
├── notifier.py         # format + send Telegram messages
├── debug.py            # write raw HTML + parsed-data dumps to disk
├── main.py             # CLI + scheduler loop
├── requirements.txt    # Python deps
├── .env                # (gitignored) Telegram credentials
├── .env.example        # template for .env
├── .gitignore
├── snapshot.json       # (generated) last known state of all 4 sources
├── debug_dump.json     # (generated) parsed rows per source
├── debug_*.html        # (generated) raw HTML per source
└── extractor.log       # (generated) runtime log
```

---

## How It Works

### Per-cycle flow

```
┌─────────────────────────────────────────────────────────────────┐
│  main.py — run_once()  (called every POLL_INTERVAL_MINUTES)     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
   ┌─────────────────────────────────────────────────────────┐
   │  1. collect_all_rows()                                  │
   │     For each of 4 sources (city × visa_type):           │
   │       a. fetcher.fetch_html(source.url)                 │
   │       b. parser.parse_appointments(html, source)        │
   │     Merge all rows into one list                        │
   ├─────────────────────────────────────────────────────────┤
   │  2. parser.py per row                                   │
   │     • Extract country (e.g. "Denmark 🇩🇰")              │
   │     • Look up VFS URL via countries.get_vfs_url()       │
   │       → https://visa.vfsglobal.com/are/en/dnk/login     │
   │     • Extract status: "21 May" / "Waitlist Open" /      │
   │       "No availability"                                 │
   │     • Classify status_type                              │
   │     • Build stable id = "city/visa_type::country"       │
   ├─────────────────────────────────────────────────────────┤
   │  3. state.load_snapshot()                               │
   │     Read snapshot.json → old_rows                       │
   ├─────────────────────────────────────────────────────────┤
   │  4. differ.diff_snapshots(old_rows, new_rows)           │
   │     • Match rows by id                                  │
   │     • Compare every field EXCEPT last_checked           │
   │     • Emit change events                                │
   ├─────────────────────────────────────────────────────────┤
   │  5. notifier.notify_events(events)                      │
   │     • Filter to became_available + date_changed only    │
   │     • Format and POST to Telegram                       │
   ├─────────────────────────────────────────────────────────┤
   │  6. state.save_snapshot(new_rows)                       │
   │     Atomically overwrite snapshot.json                  │
   └─────────────────────────────────────────────────────────┘
```

### Data model

Each parsed row looks like:

```json
{
  "country": "Denmark 🇩🇰",
  "country_url": "https://visa.vfsglobal.com/are/en/dnk/login",
  "status": "21 May",
  "status_type": "available",
  "last_checked": "38 minutes ago",
  "months": { "May": false, "Jun": false, "Jul": false },
  "source_key": "dubai/tourism",
  "city": "dubai",
  "visa_type": "tourism",
  "id": "dubai/tourism::Denmark 🇩🇰"
}
```

`status_type` is one of:
- `available` — concrete date like `21 May`, `07 Jul`
- `waitlist` — `Waitlist Open`
- `unavailable` — `No availability`
- `unknown` — fallback for unrecognised text

---

## What Triggers a Telegram Message

The differ detects **all** changes (any field except `last_checked`), but the notifier **only sends Telegram messages for events that mean a slot is bookable or has moved**.

### Event kinds and notification policy

| Event kind | Fires when… | Telegram sent? |
|---|---|---|
| **`became_available`** | Status went from waitlist/unavailable/unknown → a concrete date (e.g. Waitlist Open → 21 May) | ✅ **YES** |
| **`date_changed`** | Status was an available date and still is, but the date itself changed (e.g. 21 May → 18 May) | ✅ **YES** |
| `new_country` | A country appeared that wasn't in the previous snapshot | ❌ No |
| `became_unavailable` | Was on a concrete date, now waitlist or no availability | ❌ No |
| `status_changed` | Other transitions (e.g. waitlist ↔ no availability) | ❌ No |
| `removed` | Country dropped from the table | ❌ No |

### What counts as a "change"

A row is treated as changed if **any of these fields differ** between snapshots:

- `country`
- `country_url` (VFS link)
- `status` (`"21 May"`, `"Waitlist Open"`, `"No availability"`)
- `status_type`
- `months` (per-month availability dict)
- `source_key` / `city` / `visa_type` / `id`

The **only ignored field is `last_checked`** ("checked X minutes ago"), which ticks forward constantly and would otherwise produce a false change every run.

### Message format

```
🟢 Denmark 🇩🇰
📅 21 May
📍 Dubai • Tourism
Book now → https://visa.vfsglobal.com/are/en/dnk/login
```

Each part:
- **Country** with flag (as scraped)
- **Status** — the date or status string
- **Location line** — which city + visa type this came from (so you know whether it's Dubai/Tourism vs Abu-Dhabi/Business)
- **Book now** — direct link to the VFS Global booking page (rendered as a clickable HTML link in Telegram)

If a country has no VFS URL mapping (e.g. Cyprus), the Book-now link is omitted but the rest of the message still goes through.

---

## Setup

### 1. Install Python dependencies

```powershell
py -m pip install -r requirements.txt
```

### 2. Create a Telegram bot

1. Open Telegram, search for `@BotFather`
2. Send `/newbot`, follow the prompts
3. Save the token (e.g. `1234567890:ABC-DEF...`)

### 3. Find your chat ID

1. Send any message to your new bot
2. Open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Find `"chat":{"id":12345678,...}` — that number is your chat ID

### 4. Configure environment variables

Copy [.env.example](.env.example) → `.env` and fill in:

```
TELEGRAM_BOT_TOKEN=1234567890:ABC-DEF...
TELEGRAM_CHAT_ID=12345678
POLL_INTERVAL_MINUTES=10
SNAPSHOT_FILE=snapshot.json
LOG_FILE=extractor.log
DEBUG_DUMP_FILE=debug_dump.json
```

---

## How to Run

### Test the Telegram connection

```powershell
py main.py --test-telegram
```

Sends one test message. If it lands in your Telegram, your credentials are correct.

### One-off run

```powershell
py main.py --once
```

Fetches all 4 sources, parses, diffs against `snapshot.json`, sends change messages, then exits. Ideal for cron / Task Scheduler.

### One-off run with debug dumps

```powershell
py main.py --once --debug-dump
```

Same as `--once`, but additionally saves raw HTML and parsed-data dumps. See [Debug Dumps](#debug-dumps).

### Continuous run (default mode)

```powershell
py main.py
```

Runs forever — first check immediately, then every `POLL_INTERVAL_MINUTES` minutes. Stop with `Ctrl+C`.

### Force first-run notifications

```powershell
py main.py --once --notify-first-run
```

Sends a Telegram message for every available slot even on the very first run. Default behaviour is silent on first run.

### Run as a Windows scheduled task

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
2026-05-12 15:06:42 INFO [main]    Fetching https://schengenappointments.com/in/abu-dhabi/tourism
2026-05-12 15:06:43 INFO [parser]  Parsed 18 rows from abu-dhabi/tourism
2026-05-12 15:06:43 WARNING [parser]  No VFS code mapping for country: Cyprus
...
2026-05-12 15:06:47 INFO [main]    First run — saving baseline of 69 rows, no notifications
```

Tail it live in PowerShell:

```powershell
Get-Content extractor.log -Wait -Tail 20
```

### 2. The snapshot file

[snapshot.json](snapshot.json) holds the **last known state** of all 4 sources combined. Open it any time to inspect what the watcher believes the world looks like.

### 3. Telegram messages

The user-facing output. See [What Triggers a Telegram Message](#what-triggers-a-telegram-message) for the exact format and policy.

---

## Debug Dumps

Run `py main.py --once --debug-dump` to save inspection files:

| File | Contents |
|---|---|
| `debug_abu-dhabi_tourism.html` | Raw HTML from `https://schengenappointments.com/in/abu-dhabi/tourism` |
| `debug_abu-dhabi_business.html` | Raw HTML from the business URL |
| `debug_dubai_tourism.html` | Raw HTML |
| `debug_dubai_business.html` | Raw HTML |
| `debug_dump.json` | Parsed rows grouped by source, with row counts |

Open `debug_dump.json` to see exactly what the parser extracted from each source:

```json
{
  "timestamp": "2026-05-12T11:04:49+00:00",
  "sources": {
    "abu-dhabi/tourism": {
      "row_count": 18,
      "rows": [ ... ]
    },
    "abu-dhabi/business": { "row_count": 16, "rows": [...] },
    "dubai/tourism":      { "row_count": 19, "rows": [...] },
    "dubai/business":     { "row_count": 16, "rows": [...] }
  }
}
```

Use this when:
- A parser change needs verification
- A country isn't showing up where you expect
- You want to inspect raw HTML structure without re-fetching

---

## Snapshot Mechanics

### What `snapshot.json` is

A single JSON file storing the **last successfully-parsed state of all 4 sources combined**. It's the "memory" the differ compares against on the next run.

### Shape

```json
{
  "timestamp": "2026-05-12T11:04:49+00:00",
  "rows": [
    { "id": "dubai/tourism::Denmark 🇩🇰", "status": "21 May", ... },
    { "id": "abu-dhabi/business::Italy 🇮🇹", "status": "No availability", ... }
  ]
}
```

### Lifecycle per `run_once()`

```
1. fetch all 4 sources → 69 fresh rows
2. load_snapshot() reads snapshot.json from disk → old_rows
3. diff_snapshots(old_rows, new_rows) → events[]
4. notify_events(events) → Telegram (filtered to available-slot events)
5. save_snapshot(new_rows) → overwrites snapshot.json
```

So on cycle N+1, the snapshot from cycle N becomes the "old" baseline.

### How it's created

- **First run**: `snapshot.json` doesn't exist → `load_snapshot()` returns `{"rows": []}` → main detects empty baseline → silently saves the first ~69 rows, **no Telegram messages**
- **Subsequent runs**: loaded, compared, then overwritten

### Atomic writes

`save_snapshot()` writes to `snapshot.json.tmp` first, then calls `os.replace()`. If the program crashes mid-write, the existing snapshot stays intact — never a half-written corrupt file.

### Why a single JSON file instead of SQLite

Only the *latest* state is needed for diffing. Keeping history would require SQLite. JSON is human-readable, easy to back up, and easy to edit by hand (great for testing — change a status, run again, see the alert).

---

## Simulating a Change (end-to-end test)

To verify the full pipeline without waiting for the real site to change:

1. Run `py main.py --once` to create a baseline
2. Open `snapshot.json` and edit one country's `status` from a real date (e.g. `"21 May"`) to `"99 Dec"`, save
3. Run `py main.py --once` again
4. You should get a Telegram message saying the date changed back to `21 May`

This proves the full pipeline (fetch → parse → diff → Telegram → snapshot save) works.

Tip: to force a `became_available` event instead of `date_changed`, edit the status to `"Waitlist Open"` and `status_type` to `"waitlist"` before re-running.

---

## Configuration Reference

All settings live in `.env` (see [.env.example](.env.example)).

| Variable | Default | Purpose |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | *(required)* | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | *(required)* | Numeric chat ID where messages are sent |
| `POLL_INTERVAL_MINUTES` | `10` | How often the scheduler runs |
| `SNAPSHOT_FILE` | `snapshot.json` | Where the last-known state is stored |
| `LOG_FILE` | `extractor.log` | Runtime log path |
| `DEBUG_DUMP_FILE` | `debug_dump.json` | Path for `--debug-dump` parsed-data output |

The 4 URLs are hard-coded in [config.py](config.py):

```python
CITIES = ["abu-dhabi", "dubai"]
VISA_TYPES = ["tourism", "business"]
```

Change these constants if you need different cities/visa types.

### CLI flags

| Flag | What it does |
|---|---|
| `--once` | Run one check and exit (otherwise: scheduler loop) |
| `--test-telegram` | Send one test message and exit |
| `--notify-first-run` | Send notifications for every available slot on the first run |
| `--debug-dump` | Save raw HTML + parsed-data dumps to disk |

---

## Notes & Decisions

### Why poll every 10 minutes?

The site explicitly states data is updated "every few minutes". 10 minutes is a balance between responsiveness and being polite to their servers. You can tighten it to 5 if needed.

### Country code mapping

[countries.py](countries.py) maps country names to ISO-3 codes used by VFS Global. The mapping uses a normalisation that strips flag emojis and converts spaces to underscores, so `"Czechia 🇨🇿"` and `"Czech_Republic"` both map to `cze`.

If the site ever lists a country not in your mapping, the parser logs a warning and `country_url` is set to `null` — the row still goes through the pipeline, just without a Book-now link.

### Why HTML scraping instead of an API?

There is no documented public API. The site says: *"The data here is pulled from visa center websites as frequently as possible."* — they're scraping too. Using their HTML table as a read-only public snapshot is the practical option.

### How fragile is the parser?

Moderately. It depends on:
- A single `<table>` per page
- Status text living inside `<span class="font-bold ...">` (available/waitlist) or `<span class="text-error ...">` (no availability)
- "checked N minutes ago" inside `<span class="badge ...">`

If the site redesigns, the parser will need adjusting. The `_classify()` function in [parser.py](parser.py) is the regex layer that translates raw text into `available`/`waitlist`/`unavailable` — most format changes only need a tweak there.

### Atomic snapshot writes

`state.save_snapshot()` writes to `snapshot.json.tmp` first, then `os.replace()`s it. A crash mid-write can't corrupt the snapshot — you'll always have either the old version or the new one, never a half-written file.
