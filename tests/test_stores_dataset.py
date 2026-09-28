"""The dataset itself: 120 worldwide stores, consistent fields."""
from urllib.parse import urlsplit

import pytest

from config.sites_config import AREAS, SPECIALTIES, TYPES, load_stores

STORES = load_stores()
CURRENCIES = {
    "EUR", "GBP", "CHF", "CZK", "USD", "JPY", "HKD", "SGD", "INR", "AED",
    "TRY", "KRW",
}


def test_total_and_area_counts():
    assert len(STORES) == 120
    by_area = {a: sum(1 for s in STORES if s["area"] == a) for a in AREAS}
    assert by_area == {"europe": 37, "usa": 63, "asia": 20}


def test_ids_unique_and_slugged():
    ids = [s["id"] for s in STORES]
    assert len(set(ids)) == len(ids)
    for sid in ids:
        assert sid == sid.lower()
        assert all(c.isalnum() or c == "-" for c in sid), sid


@pytest.mark.parametrize("store", STORES, ids=[s["id"] for s in STORES])
def test_store_fields(store):
    assert store["area"] in AREAS
    assert store["specialty"] in SPECIALTIES
    assert store["type"] in TYPES
    assert isinstance(store["top"], bool)
    assert len(store["country"]) == 2 and store["country"].isupper()
    assert store["local_currency"] in CURRENCIES
    assert store["note"].strip()
    assert store["url"].startswith("http")
    # `domain` is the host without www., and must match the start URL's host.
    host = urlsplit(store["url"]).netloc.removeprefix("www.")
    assert store["domain"] == host, f"{store['id']}: {store['domain']} != {host}"


def test_us_state_only_for_usa():
    for store in STORES:
        if store["area"] == "usa":
            assert store["us_state"] and len(store["us_state"]) == 2
            assert store["country"] == "US"
        else:
            assert store["us_state"] is None


def test_closed_shops_absent():
    """Shops the source list marks as closed must never come back."""
    ids = {s["id"] for s in STORES}
    for gone in ("sam-ash", "pmt", "gak", "justmusic", "4sound", "hiren-roy"):
        assert gone not in ids
