import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TARGET_URL = os.getenv("TARGET_URL", "https://schengenappointments.com/")
POLL_INTERVAL_MINUTES = int(os.getenv("POLL_INTERVAL_MINUTES", "10"))
SNAPSHOT_FILE = os.getenv("SNAPSHOT_FILE", "snapshot.json")
LOG_FILE = os.getenv("LOG_FILE", "extractor.log")

REQUEST_TIMEOUT = 20
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 schengen-watcher/1.0"
