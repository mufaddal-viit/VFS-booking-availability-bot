import json
import logging
import os
from datetime import datetime, timezone
from config import SNAPSHOT_FILE, STATE_BUCKET, STATE_KEY

log = logging.getLogger(__name__)

_EMPTY: dict = {"timestamp": None, "rows": []}

_USE_S3 = bool(STATE_BUCKET)


def _validate(data: object) -> dict:
    """Return data if it is a valid snapshot dict, otherwise return empty."""
    if (
        isinstance(data, dict)
        and isinstance(data.get("rows"), list)
    ):
        return data
    log.warning("Snapshot has unexpected structure — starting fresh")
    return dict(_EMPTY)


# ── S3 backend ────────────────────────────────────────────────────────────────

def _s3_client():
    import boto3
    return boto3.client("s3")


def _load_from_s3() -> dict:
    try:
        resp = _s3_client().get_object(Bucket=STATE_BUCKET, Key=STATE_KEY)
        data = json.loads(resp["Body"].read())
        return _validate(data)
    except _s3_client().__class__.exceptions.NoSuchKey:
        return dict(_EMPTY)
    except Exception as e:
        log.warning("Could not load snapshot from S3 s3://%s/%s: %s — starting fresh", STATE_BUCKET, STATE_KEY, e)
        return dict(_EMPTY)


def _save_to_s3(payload: dict) -> None:
    _s3_client().put_object(
        Bucket=STATE_BUCKET,
        Key=STATE_KEY,
        Body=json.dumps(payload, ensure_ascii=False, indent=2).encode(),
        ContentType="application/json",
    )
    log.info("Snapshot saved to s3://%s/%s", STATE_BUCKET, STATE_KEY)


# ── Local file backend ────────────────────────────────────────────────────────

def _load_from_file(path: str) -> dict:
    if not os.path.exists(path):
        return dict(_EMPTY)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return _validate(json.load(f))
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Could not load snapshot %s: %s — starting fresh", path, e)
        return dict(_EMPTY)


def _save_to_file(payload: dict, path: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ── Public API ────────────────────────────────────────────────────────────────

def load_snapshot(path: str = SNAPSHOT_FILE) -> dict:
    if _USE_S3:
        return _load_from_s3()
    return _load_from_file(path)


def save_snapshot(rows: list[dict], path: str = SNAPSHOT_FILE) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
    }
    if _USE_S3:
        _save_to_s3(payload)
    else:
        _save_to_file(payload, path)
