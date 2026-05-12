"""Country name → ISO-3 code mapping for building VFS Global booking URLs."""
import re

COUNTRY_CODES: dict[str, str] = {
    "austria": "aut",
    "belgium": "bel",
    "bulgaria": "bgr",
    "croatia": "hrv",
    "czech_republic": "cze",
    "czechia": "cze",
     "cyprus": "cyp",
    "denmark": "dnk",
    "estonia": "est",
    "finland": "fin",
    "france": "fra",
    "germany": "deu",
    "greece": "grc",
    "hungary": "hun",
    "iceland": "isl",
    "italy": "ita",
    "latvia": "lva",
    "liechtenstein": "lie",
    "lithuania": "ltu",
    "luxembourg": "lux",
    "malta": "mlt",
    "netherlands": "nld",
    "norway": "nor",
    "poland": "pol",
    "portugal": "prt",
    "romania": "rou",
    "slovakia": "svk",
    "slovenia": "svn",
    "spain": "esp",
    "sweden": "swe",
    "switzerland": "che",
}

VFS_URL_TEMPLATE = "https://visa.vfsglobal.com/are/en/{code}/login"


def _normalize(country_name: str) -> str:
    """Strip flag emojis and whitespace, lowercase, replace spaces with underscores."""
    # Drop everything outside basic ASCII letters & spaces (kills flag emojis)
    cleaned = re.sub(r"[^a-zA-Z\s]", "", country_name or "")
    return cleaned.strip().lower().replace(" ", "_")


def get_vfs_url(country_name: str) -> str | None:
    """Return VFS booking URL for a country name, or None if unknown."""
    key = _normalize(country_name)
    code = COUNTRY_CODES.get(key)
    if not code:
        return None
    return VFS_URL_TEMPLATE.format(code=code)
