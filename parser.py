import logging
import re
from bs4 import BeautifulSoup

from countries import get_vfs_url

log = logging.getLogger(__name__)

NO_AVAIL_TOKENS = ("no appointments", "no availability")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _classify(status_text: str) -> str:
    s = status_text.lower()
    if "waitlist" in s:
        return "waitlist"
    if re.match(r"^\d{1,2}\s+[A-Za-z]{3}", status_text):
        return "available"
    if any(tok in s for tok in NO_AVAIL_TOKENS):
        return "unavailable"
    return "unknown"


def parse_appointments(html: str, source: dict | None = None) -> list[dict]:
    """Parse schengenappointments.com table into a list of row dicts.

    If `source` is provided (with keys: key, city, visa_type), each row
    is tagged with source_key/city/visa_type and gets a stable `id`.
    """
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if table is None:
        log.warning("No <table> found in HTML")
        return []

    thead = table.find("thead")
    month_headers: list[str] = []
    if thead:
        ths = thead.find_all("th")
        # Skip first two columns (country, earliest available)
        for th in ths[2:]:
            month_headers.append(_clean(th.get_text()))

    tbody = table.find("tbody")
    if tbody is None:
        return []

    rows: list[dict] = []
    for tr in tbody.find_all("tr"):
        cells = tr.find_all(["th", "td"], recursive=False)
        if len(cells) < 2:
            continue

        country_cell = cells[0]
        status_cell = cells[1]
        month_cells = cells[2:]

        country_link = country_cell.find("a")
        country = _clean(country_link.get_text()) if country_link else _clean(country_cell.get_text())
        country_url = get_vfs_url(country)
        if not country_url:
            # Strip non-ASCII (flag emojis) so Windows console can log it safely
            safe_name = country.encode("ascii", "ignore").decode("ascii").strip()
            log.warning("No VFS code mapping for country: %s", safe_name)

        # Status text — try font-bold (available/waitlist) then text-error (no availability)
        status_span = (
            status_cell.find("span", class_=re.compile(r"font-bold"))
            or status_cell.find("span", class_=re.compile(r"text-error"))
        )
        if status_span:
            status = _clean(status_span.get_text())
        else:
            # Fallback: strip out badge + notify-me, take what's left
            cell_copy = BeautifulSoup(str(status_cell), "lxml")
            for tag in cell_copy.find_all("span", class_=re.compile(r"badge|notify")):
                tag.decompose()
            status = _clean(cell_copy.get_text())

        checked_span = status_cell.find("span", class_=re.compile(r"badge"))
        last_checked = _clean(checked_span.get_text()) if checked_span else ""
        last_checked = re.sub(r"^checked\s*", "", last_checked, flags=re.IGNORECASE)

        months: dict[str, bool] = {}
        for i, mc in enumerate(month_cells):
            if i >= len(month_headers):
                break
            tip = ""
            a = mc.find("a")
            if a and a.has_attr("data-tip"):
                tip = a["data-tip"].lower()
            months[month_headers[i]] = not any(tok in tip for tok in NO_AVAIL_TOKENS) if tip else False

        row = {
            "country": country,
            "country_url": country_url,
            "status": status,
            "status_type": _classify(status),
            "last_checked": last_checked,
            "months": months,
        }
        if source:
            row["source_key"] = source.get("key")
            row["city"] = source.get("city")
            row["visa_type"] = source.get("visa_type")
            row["id"] = f"{source.get('key')}::{country}"
        else:
            row["id"] = country
        rows.append(row)

    src_label = source.get("key") if source else "default"
    log.info("Parsed %d rows from %s", len(rows), src_label)
    return rows
