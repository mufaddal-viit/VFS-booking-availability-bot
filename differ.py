import logging

log = logging.getLogger(__name__)


def _index_by_country(rows: list[dict]) -> dict[str, dict]:
    return {r["country"]: r for r in rows}


def diff_snapshots(old_rows: list[dict], new_rows: list[dict]) -> list[dict]:
    """Return a list of change events.

    Event shape: { country, kind, old, new }
    kind in: new_country, became_available, became_unavailable, date_changed,
             status_changed, removed
    """
    old = _index_by_country(old_rows)
    new = _index_by_country(new_rows)
    events: list[dict] = []

    for country, n in new.items():
        o = old.get(country)
        if o is None:
            events.append({
                "country": country,
                "kind": "new_country",
                "old": None,
                "new": n,
            })
            continue

        # Only compare status, ignore last_checked time (it always changes)
        old_status = (o.get("status") or "").strip()
        new_status = (n.get("status") or "").strip()
        if old_status == new_status:
            continue

        old_type = o.get("status_type")
        new_type = n.get("status_type")

        if new_type == "available" and old_type != "available":
            kind = "became_available"
        elif old_type == "available" and new_type != "available":
            kind = "became_unavailable"
        elif old_type == "available" and new_type == "available":
            kind = "date_changed"
        else:
            kind = "status_changed"

        events.append({
            "country": country,
            "kind": kind,
            "old": o,
            "new": n,
        })

    for country, o in old.items():
        if country not in new:
            events.append({
                "country": country,
                "kind": "removed",
                "old": o,
                "new": None,
            })

    log.info("Diff produced %d events", len(events))
    return events
