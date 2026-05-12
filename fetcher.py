import logging
import requests
from config import TARGET_URL, REQUEST_TIMEOUT, USER_AGENT

log = logging.getLogger(__name__)


def fetch_html(url: str = TARGET_URL) -> str | None:
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        # print(resp.text)
        return resp.text
    except requests.RequestException as e:
        log.error("Failed to fetch %s: %s", url, e)
        return None
