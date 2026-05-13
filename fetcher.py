import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from config import REQUEST_TIMEOUT, USER_AGENT

log = logging.getLogger(__name__)


def fetch_html(url: str) -> str | None:
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        log.error("Failed to fetch %s: %s", url, e)
        return None


def fetch_all(sources: list[dict]) -> dict[str, str | None]:
    """Fetch all source URLs concurrently. Returns {source_key: html | None}."""
    results: dict[str, str | None] = {}

    with ThreadPoolExecutor(max_workers=len(sources)) as executor:
        future_to_src = {
            executor.submit(fetch_html, src["url"]): src
            for src in sources
        }
        for future in as_completed(future_to_src):
            src = future_to_src[future]
            try:
                results[src["key"]] = future.result()
            except Exception as e:
                log.error("Unexpected error fetching %s: %s", src["key"], e)
                results[src["key"]] = None

    return results
