"""Assertions over the last live run of ``scripts/test_all_stores.py``.

The network work happens in that script (it is slow and rate-limited); pytest
only checks its report, so the suite stays fast and deterministic. Refresh with:

    python -m scripts.test_all_stores
"""
import json
from pathlib import Path

import pytest

from config.sites_config import SITES_CONFIG

REPORT = Path(__file__).resolve().parents[1] / "data" / "store_test_report.json"
MIN_PASSING = 55  # regression floor: a config change must not silently gut coverage


def _report() -> dict:
    if not REPORT.exists():
        pytest.skip("no store_test_report.json — run python -m scripts.test_all_stores")
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_report_covers_every_store():
    stores = _report()["stores"]
    assert set(stores) == set(SITES_CONFIG)


def test_no_store_failed_or_misconfigured():
    stores = _report()["stores"]
    broken = {
        k: v.get("error") or v.get("result")
        for k, v in stores.items()
        if v.get("result") in ("failed", "misconfigured")
    }
    assert not broken, f"stores expected to return offers but returned none: {broken}"


def test_passing_stores_returned_usable_offers():
    stores = _report()["stores"]
    passed = {k: v for k, v in stores.items() if v.get("result") == "passed"}
    assert len(passed) >= MIN_PASSING, f"only {len(passed)} stores returned offers"
    with_url = 0
    for key, res in passed.items():
        assert res["offers_found"] >= 1
        sample = res["sample"]
        assert sample, key
        for offer in sample:
            assert offer["name"]
            assert offer["price"] and offer["price"] > 0
            assert offer["price_eur"] and offer["price_eur"] > 0
        if all(o.get("url") for o in sample):
            with_url += 1
    # Product links come from every route except a few embedded catalogues that
    # simply do not carry them; keep that the rare exception.
    assert with_url >= 0.9 * len(passed), (
        f"only {with_url}/{len(passed)} stores returned product links"
    )


def test_skipped_stores_are_documented():
    stores = _report()["stores"]
    for key, res in stores.items():
        if res.get("result") == "skipped":
            assert res.get("blocked_reason"), f"{key} skipped without a reason"
            assert not SITES_CONFIG[key]["enabled"] or not SITES_CONFIG[key]["searchable"]


def test_every_area_has_working_stores():
    stores = _report()["stores"]
    working = {SITES_CONFIG[k]["area"] for k, v in stores.items() if v.get("result") == "passed"}
    assert working == {"europe", "usa", "asia"}
