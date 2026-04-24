"""Test per scraper_service.py."""

import pytest

try:
    from scraper_service import filter_and_rank_results, calculate_discounts, get_top_discounts
    SERVICE_AVAILABLE = True
except ImportError:
    SERVICE_AVAILABLE = False

skip_if_missing = pytest.mark.skipif(
    not SERVICE_AVAILABLE, reason="scraper_service.py non trovato"
)

ITEMS_WITH_NAME = [
    {"nome": f"Chitarra Modello {i}", "prezzo_numerico": 100.0 * i,
     "prezzo": f"{100*i},00", "sito": "Test", "link": f"http://test.com/{i}",
     "prezzo_originale_numerico": 0, "immagine": ""}
    for i in range(1, 11)
]


@skip_if_missing
def test_calculate_discounts_with_discount():
    items = [{"prezzo_numerico": 500.0, "prezzo_originale_numerico": 600.0}]
    result = calculate_discounts(items)
    assert result[0]["sconto_percentuale"] == 17


@skip_if_missing
def test_calculate_discounts_no_discount():
    items = [{"prezzo_numerico": 500.0, "prezzo_originale_numerico": 0.0}]
    result = calculate_discounts(items)
    assert result[0]["sconto_percentuale"] == 0


@skip_if_missing
def test_calculate_discounts_same_price():
    items = [{"prezzo_numerico": 500.0, "prezzo_originale_numerico": 500.0}]
    result = calculate_discounts(items)
    assert result[0]["sconto_percentuale"] == 0


@skip_if_missing
def test_filter_and_rank_strict_mode():
    items = [
        {"nome": "Chitarra Fender", "prezzo_numerico": 500.0, "prezzo": "500",
         "sito": "Test", "link": "http://a.com", "prezzo_originale_numerico": 0, "immagine": ""},
    ] * 6  # 6 item con "chitarra" nel nome → strict mode
    ranked, mode = filter_and_rank_results(items, "chitarra")
    assert mode == "strict"


@skip_if_missing
def test_filter_and_rank_fuzzy_fallback():
    items = [
        {"nome": "Chitarra Fender", "prezzo_numerico": 500.0, "prezzo": "500",
         "sito": "Test", "link": "http://a.com", "prezzo_originale_numerico": 0, "immagine": ""},
        {"nome": "Basso Fender", "prezzo_numerico": 300.0, "prezzo": "300",
         "sito": "Test2", "link": "http://b.com", "prezzo_originale_numerico": 0, "immagine": ""},
    ]
    ranked, mode = filter_and_rank_results(items, "chitarra")
    assert mode == "fuzzy"


@skip_if_missing
def test_get_top_discounts():
    items = [
        {"sconto_percentuale": 20, "nome": "A"},
        {"sconto_percentuale": 0, "nome": "B"},
        {"sconto_percentuale": 35, "nome": "C"},
        {"sconto_percentuale": 10, "nome": "D"},
    ]
    top = get_top_discounts(items, n=2)
    assert len(top) == 2
    assert top[0]["sconto_percentuale"] == 35
    assert top[1]["sconto_percentuale"] == 20
