import logging

log = logging.getLogger(__name__)

# Fields ignored entirely — never compared, never listed in changed_fields
IGNORED_FIELDS = {"last_checked", "source_key", "city", "visa_type", "country_url", "id"}

# The fields that actually reflect appointment availability
AVAILABILITY_FIELDS = {"status", "status_type", "months"}


def _row_key(row: dict) -> str:
    return row.get("id") or row.get("country") or ""


def _index(rows: list[dict]) -> dict[str, dict]:
    return {_row_key(r): r for r in rows if _row_key(r)}


def _availability(row: dict) -> dict:
    """Extract only availability-relevant fields for comparison."""
    return {k: v for k, v in row.items() if k in AVAILABILITY_FIELDS}


def _classify_change(old: dict, new: dict) -> str:
    old_type = old.get("status_type")
    new_type = new.get("status_type")
    if new_type == "available" and old_type != "available":
        return "became_available"
    if old_type == "available" and new_type != "available":
        return "became_unavailable"
    if old_type == "available" and new_type == "available":
        return "date_changed"
    return "status_changed"


def diff_snapshots(old_rows: list[dict], new_rows: list[dict]) -> list[dict]:
    """Compare old vs new rows on availability fields only (status, status_type, months).

    last_checked and other metadata fields are completely ignored.

    Event shape: { id, country, source_key, kind, old, new, changed_fields }
    kind in: new_country, became_available, became_unavailable, status_changed, removed
    """
    old = _index(old_rows)
    new = _index(new_rows)
    events: list[dict] = []

    for row_id, n in new.items():
        o = old.get(row_id)
        if o is None:
            events.append({
                "id": row_id,
                "country": n.get("country"),
                "source_key": n.get("source_key"),
                "kind": "new_country",
                "old": None,
                "new": n,
                "changed_fields": list(_availability(n).keys()),
            })
            continue

        old_avail = _availability(o)
        new_avail = _availability(n)
        if old_avail == new_avail:
            continue

        changed = [k for k in AVAILABILITY_FIELDS if old_avail.get(k) != new_avail.get(k)]
        events.append({
            "id": row_id,
            "country": n.get("country"),
            "source_key": n.get("source_key"),
            "kind": _classify_change(o, n),
            "old": o,
            "new": n,
            "changed_fields": changed,
        })

    for row_id, o in old.items():
        if row_id not in new:
            events.append({
                "id": row_id,
                "country": o.get("country"),
                "source_key": o.get("source_key"),
                "kind": "removed",
                "old": o,
                "new": None,
                "changed_fields": [],
            })

    log.info("Diff produced %d events", len(events))
    return events
