import json
import logging
import os
from datetime import datetime, timezone
from config import SNAPSHOT_FILE

log = logging.getLogger(__name__)


def load_snapshot(path: str = SNAPSHOT_FILE) -> dict:
    if not os.path.exists(path):
        return {"timestamp": None, "rows": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Could not load snapshot %s: %s — starting fresh", path, e)
        return {"timestamp": None, "rows": []}


def save_snapshot(rows: list[dict], path: str = SNAPSHOT_FILE) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
