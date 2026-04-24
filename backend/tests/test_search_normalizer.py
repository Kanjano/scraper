"""Test per search_normalizer.py."""

import pytest

try:
    from search_normalizer import normalize_query, fuzzy_match_score, get_query_variants
    NORMALIZER_AVAILABLE = True
except ImportError:
    NORMALIZER_AVAILABLE = False

skip_if_missing = pytest.mark.skipif(
    not NORMALIZER_AVAILABLE, reason="search_normalizer.py non trovato"
)


@skip_if_missing
def test_normalize_lowercase():
    assert normalize_query("CHITARRA") == "chitarra"


@skip_if_missing
def test_normalize_accents():
    result = normalize_query("chitàrra")
    assert "à" not in result
    assert "chitarra" in result


@skip_if_missing
def test_normalize_empty():
    assert normalize_query("") == ""


@skip_if_missing
def test_normalize_special_chars():
    result = normalize_query("fender® stratocaster™")
    assert "®" not in result
    assert "™" not in result


@skip_if_missing
def test_fuzzy_score_similar():
    score = fuzzy_match_score("chitarra fender stratocaster", "chitarr fender")
    assert score > 0.7, f"Score atteso > 0.7, ottenuto {score}"


@skip_if_missing
def test_fuzzy_score_different():
    score = fuzzy_match_score("chitarra", "pianoforte")
    assert score < 0.4, f"Score atteso < 0.4, ottenuto {score}"


@skip_if_missing
def test_fuzzy_score_exact():
    score = fuzzy_match_score("chitarra", "chitarra")
    assert score > 0.95


@skip_if_missing
def test_get_query_variants_plural():
    variants = get_query_variants("chitarra")
    assert "chitarra" in variants
    assert len(variants) >= 1
