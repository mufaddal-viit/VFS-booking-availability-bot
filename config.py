import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

POLL_INTERVAL_MINUTES = int(os.getenv("POLL_INTERVAL_MINUTES", "10"))
SNAPSHOT_FILE = os.getenv("SNAPSHOT_FILE", "snapshot.json")
LOG_FILE = os.getenv("LOG_FILE", "extractor.log")
DEBUG_DUMP_FILE = os.getenv("DEBUG_DUMP_FILE", "debug_dump.json")

REQUEST_TIMEOUT = 20
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 schengen-watcher/1.0"

BASE_URL = "https://schengenappointments.com"
CITIES = ["abu-dhabi", "dubai"]
VISA_TYPES = ["tourism", "business"]


def build_sources() -> list[dict]:
    """Return a list of source dicts to scrape.

    Each source: { key, city, visa_type, url }
    """
    sources: list[dict] = []
    for city in CITIES:
        for visa in VISA_TYPES:
            sources.append({
                "key": f"{city}/{visa}",
                "city": city,
                "visa_type": visa,
                "url": f"{BASE_URL}/in/{city}/{visa}",
            })
    return sources


SOURCES = build_sources()
