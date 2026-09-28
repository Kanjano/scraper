"""Pick the page language from the country the visitor connects from.

Order of precedence:
  1. an explicit choice (``?lang=`` or the ``lang`` cookie it sets);
  2. the visitor's country — from the CDN header when there is one
     (Cloudflare, CloudFront, Vercel, App Engine), otherwise from the client IP
     through the offline DB-IP Lite database — mapped to the languages spoken
     there (CLDR data via Babel). In a multilingual country the browser's
     ``Accept-Language`` picks among them (a French speaker in Switzerland);
  3. ``Accept-Language`` alone, for countries without a supported language;
  4. English.

The GeoIP file is optional: without it (``GEOIP_DB`` missing) step 2 relies on
the CDN header only. Refresh it monthly:
  curl -s https://download.db-ip.com/free/dbip-country-lite-YYYY-MM.mmdb.gz \
    | gunzip > data/dbip-country-lite.mmdb
"""
import ipaddress
import json
from functools import lru_cache
from pathlib import Path

from babel import Locale
from babel.languages import get_official_languages
from starlette.requests import Request

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

TRANSLATIONS: dict[str, dict[str, str]] = json.loads(
    (Path(__file__).parent / "web" / "translations.json").read_text(encoding="utf-8")
)
SUPPORTED = tuple(TRANSLATIONS)
DEFAULT = "en"

# Country code set by the CDN / platform in front of the app.
_COUNTRY_HEADERS = (
    "cf-ipcountry",
    "cloudfront-viewer-country",
    "x-vercel-ip-country",
    "x-appengine-country",
    "x-country-code",
)


def _supported(tag: str) -> str | None:
    """Map a BCP 47 / CLDR tag ("pt-BR", "zh_Hant", "zh-TW") to a supported code."""
    tag = tag.strip().replace("-", "_")
    if not tag:
        return None
    lang, _, rest = tag.partition("_")
    lang = lang.lower()
    if lang == "zh":
        # Traditional script: explicit Hant, or the regions that write it.
        return "zh_Hant" if rest.split("_")[0].upper() in ("HANT", "TW", "HK", "MO") else "zh"
    return lang if lang in SUPPORTED else None


def _accept_language(header: str | None) -> list[str]:
    """Supported languages from Accept-Language, best quality first."""
    ranked = []
    for i, part in enumerate((header or "").split(",")):
        tag, _, q = part.strip().partition(";q=")
        try:
            weight = float(q) if q else 1.0
        except ValueError:
            weight = 0.0
        code = _supported(tag)
        if code and weight > 0:
            ranked.append((-weight, i, code))
    return list(dict.fromkeys(code for *_, code in sorted(ranked)))


@lru_cache(maxsize=1)
def _geoip():
    path = Path(settings.geoip_db)
    if not path.exists():
        logger.warning("GeoIP database %s not found: country from CDN headers only", path)
        return None
    import maxminddb

    return maxminddb.open_database(str(path))


def _client_ip(request: Request) -> str | None:
    # Behind a proxy the visitor is the first X-Forwarded-For hop. It can be
    # spoofed, which here only changes the page language.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def country_of(request: Request) -> str | None:
    for header in _COUNTRY_HEADERS:
        code = (request.headers.get(header) or "").strip().upper()
        if len(code) == 2 and code.isalpha() and code not in ("XX", "T1"):
            return code
    ip, db = _client_ip(request), _geoip()
    if not ip or db is None:
        return None
    try:
        if not ipaddress.ip_address(ip).is_global:
            return None
        record = db.get(ip)
    except ValueError:
        return None
    return ((record or {}).get("country") or {}).get("iso_code")


def country_languages(country: str | None) -> list[str]:
    if not country:
        return []
    codes = (_supported(c) for c in get_official_languages(country, de_facto=True))
    return list(dict.fromkeys(c for c in codes if c))


def pick_language(request: Request) -> tuple[str, str | None]:
    """(language, country) for this request."""
    explicit = _supported(request.query_params.get("lang") or request.cookies.get("lang") or "")
    country = country_of(request)
    if explicit:
        return explicit, country
    browser = _accept_language(request.headers.get("accept-language"))
    local = country_languages(country)
    if local:
        preferred = next((b for b in browser if b in local), None)
        return preferred or local[0], country
    return (browser[0] if browser else DEFAULT), country


def text_direction(lang: str) -> str:
    return "rtl" if Locale.parse(lang).character_order == "right-to-left" else "ltr"


def autonym(lang: str) -> str:
    """The language's name in itself, for the language picker."""
    name = Locale.parse(lang).get_display_name(lang)
    return name[:1].upper() + name[1:]


def html_lang(lang: str) -> str:
    return lang.replace("_", "-")
