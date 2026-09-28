"""Shop icons for the search page, served from our own origin.

Loading each shop's favicon straight from the browser would contact ~80 shop
domains per search (their cookies, the visitor's IP, 404 noise in the console).
The server fetches each icon once, keeps it on disk, and falls back to a letter
badge when a shop has none.
"""
import re
from html import escape
from pathlib import Path
from urllib.parse import urljoin

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from config.sites_config import SITES_CONFIG
from utils.logger import get_logger

router = APIRouter(tags=["ui"])
logger = get_logger(__name__)

CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "favicons"
_ICON_LINK = re.compile(
    r"<link[^>]+rel=[\"'][^\"']*icon[^\"']*[\"'][^>]*>", re.I
)
_HREF = re.compile(r"href=[\"']([^\"']+)[\"']", re.I)
_WEEK = "public, max-age=604800, immutable"


def _letter_svg(name: str) -> bytes:
    letter = escape((name or "?").strip()[:1].upper() or "?")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        '<rect width="32" height="32" rx="16" fill="#e8eaed"/>'
        f'<text x="16" y="21.5" text-anchor="middle" font-family="system-ui,sans-serif" '
        f'font-size="15" font-weight="600" fill="#5f6368">{letter}</text></svg>'
    ).encode()


def _fetch_icon(base_url: str) -> tuple[bytes, str] | None:
    from curl_cffi import requests as curl_requests  # a browser fingerprint: fewer 403s

    def image(url: str):
        r = session.get(url, timeout=6)
        kind = (r.headers.get("content-type") or "").split(";")[0].strip()
        if r.status_code == 200 and r.content and (kind.startswith("image/") or url.endswith(".ico")):
            return r.content, kind if kind.startswith("image/") else "image/x-icon"
        return None

    with curl_requests.Session(impersonate="chrome") as session:
        try:
            if found := image(urljoin(base_url + "/", "favicon.ico")):
                return found
            home = session.get(base_url, timeout=8).text
            for tag in _ICON_LINK.findall(home)[:3]:
                if (href := _HREF.search(tag)) and (found := image(urljoin(base_url + "/", href.group(1)))):
                    return found
        except Exception as exc:  # noqa: BLE001 — any failure means "no icon"
            logger.info("no favicon for %s: %s", base_url, exc)
    return None


@router.get("/favicon/{site_key}", include_in_schema=False)
def favicon(site_key: str):
    cfg = SITES_CONFIG.get(site_key)
    if cfg is None:
        raise HTTPException(404)
    CACHE.mkdir(parents=True, exist_ok=True)
    # File name: "<site>__<type with / as _>" ("thomann__image_x-icon").
    for path in CACHE.glob(f"{site_key}__*"):
        kind = path.name.split("__", 1)[1].replace("_", "/", 1)
        return Response(path.read_bytes(), media_type=kind, headers={"Cache-Control": _WEEK})
    # A shop without an icon gets a letter badge, remembered so it is not asked again.
    body, kind = _fetch_icon(cfg["url"]) or (_letter_svg(cfg["name"]), "image/svg+xml")
    (CACHE / f"{site_key}__{kind.replace('/', '_', 1)}").write_bytes(body)
    return Response(body, media_type=kind, headers={"Cache-Control": _WEEK})
