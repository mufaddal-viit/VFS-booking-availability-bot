"""Debug dumps for inspecting what we fetch and what we extract.

Files written to the project directory:
  debug_dump.json    - parsed rows for every source (latest run)
  debug_<source>.html - raw HTML for each source
"""
import json
import logging
import os
from datetime import datetime, timezone

from config import DEBUG_DUMP_FILE

log = logging.getLogger(__name__)


def dump_html(html: str, source_key: str) -> str:
    """Save raw HTML for a single source. Returns the path."""
    safe = source_key.replace("/", "_")
    path = f"debug_{safe}.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def dump_parsed(all_rows_by_source: dict[str, list[dict]], path: str = DEBUG_DUMP_FILE) -> None:
    """Save parsed-row dumps for all sources to a single JSON file."""
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources": {},
    }
    for src_key, rows in all_rows_by_source.items():
        payload["sources"][src_key] = {
            "row_count": len(rows),
            "rows": rows,
        }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    log.info("Wrote debug dump to %s (%d sources)", path, len(all_rows_by_source))
