"""Search results must match what was typed; parts rank after the items."""
from scheduler.orchestrator import ScraperOrchestrator


def _offer(name, eur, site="s", brand=None):
    return {"name": name, "brand": brand, "price": eur, "price_eur_equivalent": eur,
            "site": site, "site_key": site, "url": f"https://x/{name}"}


def test_query_words_all_required_and_parts_ranked_last():
    raw = [
        _offer("Fender Custom Shop '56 Strat Relic", 4000),
        _offer("Custom Shop '57 Stratocaster with Matching Neck", 4400, brand="Fender"),
        _offer("Fender Custom Shop Fat '50s Stratocaster Pickup Set", 280),
        _offer("Fender Custom Shop Fat '50s Stratocaster Pickup Set", 280),  # duplicate
        _offer("Slate Digital Custom Series Bundle", 99),
        _offer("Fender Telecaster Custom Shop", 3500),
        _offer("Ordo Flat Patch Cable 10cm", 5),
    ]
    out = ScraperOrchestrator().aggregate_results("Fender Stratocaster Custom Shop", raw, 0.1)
    names = [r["name"] for r in out["results"]]
    assert names == [
        "Fender Custom Shop '56 Strat Relic",
        "Custom Shop '57 Stratocaster with Matching Neck",
        "Fender Custom Shop Fat '50s Stratocaster Pickup Set",
    ]
    assert out["results"][-1]["is_accessory"]
    assert out["lowest_price"] == 4000 and out["market_average"] == 4200


def test_queries_are_translated_to_english_locally():
    from scrapers.query_translation import to_english

    assert to_english("fender stratocaster custom shop") is None  # already English
    assert to_english("chitarra elettrica fender") == "guitar electric fender"
    assert to_english("batteria elettronica roland") == "drums electronic roland"
    assert to_english("Verstärker Marshall") == "amplifier marshall"
    assert to_english("sax alto yamaha") is None  # "alto" stays: not a viola here
    assert to_english("エレキギター フェンダー") == "electric guitar フェンダー"
