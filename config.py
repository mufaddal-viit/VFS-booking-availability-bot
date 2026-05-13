import json
import logging
import os

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

# ── Telegram credentials ──────────────────────────────────────────────────────
# On Lambda: set SECRETS_ARN to an AWS Secrets Manager secret that contains
# {"TELEGRAM_BOT_TOKEN": "...", "TELEGRAM_CHAT_ID": "..."}
# Locally: use .env file.

def _load_secrets_from_aws(arn: str) -> dict:
    try:
        import boto3
        client = boto3.client("secretsmanager")
        resp = client.get_secret_value(SecretId=arn)
        return json.loads(resp["SecretString"])
    except Exception as e:
        log.error("Failed to load secrets from Secrets Manager (%s): %s", arn, e)
        return {}


_SECRETS_ARN = os.getenv("SECRETS_ARN", "")
_secrets: dict = _load_secrets_from_aws(_SECRETS_ARN) if _SECRETS_ARN else {}

TELEGRAM_BOT_TOKEN: str = _secrets.get("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = _secrets.get("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID", "")

# ── State storage ─────────────────────────────────────────────────────────────
# STATE_BUCKET: S3 bucket name — if set, state.py uses S3 instead of local file
STATE_BUCKET: str = os.getenv("STATE_BUCKET", "")
STATE_KEY: str = os.getenv("STATE_KEY", "snapshot.json")

# ── Local file paths (unused on Lambda) ───────────────────────────────────────
POLL_INTERVAL_MINUTES = int(os.getenv("POLL_INTERVAL_MINUTES", "10"))
SNAPSHOT_FILE = os.getenv("SNAPSHOT_FILE", "snapshot.json")
LOG_FILE = os.getenv("LOG_FILE", "extractor.log")
DEBUG_DUMP_FILE = os.getenv("DEBUG_DUMP_FILE", "debug_dump.json")

# ── HTTP ──────────────────────────────────────────────────────────────────────
REQUEST_TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 schengen-watcher/1.0"

# ── Scrape targets ────────────────────────────────────────────────────────────
BASE_URL = "https://schengenappointments.com"
CITIES = ["abu-dhabi", "dubai"]
VISA_TYPES = ["tourism", "business"]


def build_sources() -> list[dict]:
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
