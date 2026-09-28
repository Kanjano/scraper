"""Reachability check for every configured store (including disabled ones)."""
from concurrent.futures import ThreadPoolExecutor

import requests

from config.sites_config import SITES_CONFIG, DEFAULT_USER_AGENT
from utils.logger import get_logger

logger = get_logger(__name__)
_HEADERS = {"User-Agent": DEFAULT_USER_AGENT}


def check_site(url: str, timeout: int = 15) -> bool:
    """HEAD first, GET as fallback: several shops answer 405 to HEAD."""
    for method in (requests.head, requests.get):
        try:
            resp = method(url, timeout=timeout, allow_redirects=True, headers=_HEADERS)
            if resp.status_code < 400:
                return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("health check %s failed: %s", url, exc)
    return False


def check_all(max_workers: int = 10) -> dict[str, bool]:
    keys = list(SITES_CONFIG)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = pool.map(lambda k: check_site(SITES_CONFIG[k]["url"]), keys)
    return dict(zip(keys, results))
