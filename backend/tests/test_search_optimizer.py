"""Tests for AdaptiveSearchOptimizer — covers the spec checklist:
- click learning improves correlation_score (and therefore ranking)
- variant generation produces ≥5 entries for canonical names
- failure tracking persists zero-result queries
- enrich_index adds variants for new products
- synonym matching: "strat" surfaces "Fender Stratocaster" via suggestions
"""

import pytest

from search_optimizer import (
    AdaptiveSearchOptimizer, generate_variants, product_key_from_item,
)


# -----------------------------------------------------------------------------
# Pure helpers (no DB)
# -----------------------------------------------------------------------------

def test_generate_variants_stratocaster_min_5():
    variants = generate_variants("Fender American Professional Stratocaster")
    assert len(variants) >= 5
    assert "strat" in variants
    assert any("fender" in v for v in variants)


def test_generate_variants_les_paul_lp_abbrev():
    variants = generate_variants("Gibson Les Paul Standard 60s")
    assert "lp" in variants
    assert "les paul" in variants
    assert any("gibson" in v and "lp" in v for v in variants)


def test_generate_variants_strips_series_noise():
    variants = generate_variants("Fender American Professional II Stratocaster")
    # Noise-stripped variant should exist somewhere
    assert any("professional" not in v and "ii" not in v.split() for v in variants)


def test_generate_variants_yamaha_dash_normalization():
    variants = generate_variants("Yamaha P-125")
    assert "p125" in variants or "p 125" in variants


def test_product_key_url_stable():
    a = {"link": "https://www.thomann.de/it/fender_strat.htm?ref=123"}
    b = {"link": "https://thomann.de/it/fender_strat.htm"}
    assert product_key_from_item(a) == product_key_from_item(b)


def test_product_key_fallback_when_no_url():
    item = {"nome": "Fender Stratocaster", "sito": "Thomann"}
    pk = product_key_from_item(item)
    assert pk.startswith("thomann:")
    assert "fender" in pk


# -----------------------------------------------------------------------------
# DB-backed (use conftest.py app fixture for in-memory SQLite)
# -----------------------------------------------------------------------------

@pytest.fixture
def optimizer(app):
    with app.app_context():
        yield AdaptiveSearchOptimizer()


def test_record_no_result_logs_and_alerts(app, optimizer):
    with app.app_context():
        info = optimizer.record_no_result("fender jazzmaster vintage")
        assert info["failures"] == 1
        assert info["alert"] is False
        # Trip the threshold (default 5)
        for _ in range(5):
            optimizer.record_no_result("fender jazzmaster vintage")
        info = optimizer.record_no_result("fender jazzmaster vintage")
        assert info["failures"] >= 5
        assert info["alert"] is True


def test_failed_queries_grouped(app, optimizer):
    with app.app_context():
        for _ in range(3):
            optimizer.record_no_result("ibanez jem")
        optimizer.record_no_result("prs silver sky")
        out = optimizer.get_failed_queries(limit=10)
        names = {row["query"]: row["failures"] for row in out}
        assert names.get("ibanez jem") == 3
        assert names.get("prs silver sky") == 1


def test_click_increases_correlation_score(app, optimizer):
    with app.app_context():
        product = {
            "nome": "Fender American Professional Stratocaster",
            "link": "https://thomann.de/it/fender-strat-am-pro.htm",
            "sito": "Thomann",
        }
        pk = product_key_from_item(product)
        before = optimizer.get_correlation_score("fender strat", pk)
        assert before == 0.0

        for rank in range(5):
            optimizer.record_click(None, "fender strat", product, rank=rank)

        after = optimizer.get_correlation_score("fender strat", pk)
        assert after > before
        assert 0.0 < after <= 1.0


def test_click_then_search_boosts_ranking(app, optimizer):
    with app.app_context():
        clicked = {
            "nome": "Fender American Professional Stratocaster",
            "link": "https://thomann.de/it/fender-strat-am-pro.htm",
            "sito": "Thomann",
            "relevance_score": 70,
        }
        not_clicked = {
            "nome": "Squier Affinity Stratocaster",
            "link": "https://thomann.de/it/squier-aff-strat.htm",
            "sito": "Thomann",
            "relevance_score": 75,  # starts higher to make the test meaningful
        }

        # Several clicks on the Fender for "fender strat"
        for r in range(3):
            optimizer.record_click(None, "fender strat", clicked, rank=r)
        # Mark impressions for both so the smoothed score reflects calibration
        optimizer.record_impression(
            None, "fender strat", 2,
            shown_product_keys=[
                product_key_from_item(clicked),
                product_key_from_item(not_clicked),
            ],
        )

        results = optimizer.search("fender strat", [clicked, not_clicked])
        # Clicked product should rank first now even though its base relevance
        # was lower
        assert results[0]["nome"].startswith("Fender")


def test_enrich_index_adds_new_variants(app, optimizer):
    with app.app_context():
        products = [
            {
                "nome": "Gibson Les Paul Standard",
                "link": "https://thomann.de/it/gibson-lp-std.htm",
                "sito": "Thomann",
            },
            {
                "nome": "Fender Player Telecaster",
                "link": "https://thomann.de/it/fender-player-tele.htm",
                "sito": "Thomann",
            },
        ]
        stats = optimizer.enrich_index(products)
        assert stats["scanned"] == 2
        assert stats["new_products"] == 2
        assert stats["new_variants"] > 0

        # Re-running should NOT duplicate variants
        stats2 = optimizer.enrich_index(products)
        assert stats2["new_variants"] == 0


def test_suggestion_returns_strat_for_str_prefix(app, optimizer):
    with app.app_context():
        product = {
            "nome": "Fender Stratocaster",
            "link": "https://thomann.de/it/fender-strat.htm",
            "sito": "Thomann",
        }
        optimizer.enrich_index([product])
        suggestions = optimizer.get_suggestions("str", count=5)
        assert any("strat" in s for s in suggestions)


def test_training_stats_counts(app, optimizer):
    with app.app_context():
        product = {
            "nome": "PRS Silver Sky",
            "link": "https://thomann.de/it/prs-ss.htm",
            "sito": "Thomann",
        }
        optimizer.record_click(None, "silver sky", product, rank=0)
        optimizer.record_no_result("nonexistent xyz")
        optimizer.enrich_index([product])

        stats = optimizer.get_training_stats()
        assert stats["clicks"] >= 1
        assert stats["failures"] >= 1
        assert stats["variants"] >= 1
        assert stats["correlations"] >= 1
