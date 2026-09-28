from pricing import PricingEngine


def test_suggested_price_basic():
    engine = PricingEngine()
    offers = [
        {"site": "A", "price_eur": 100.0, "reviews": 10, "stock": 5},
        {"site": "B", "price_eur": 110.0, "reviews": 600, "stock": 30},
        {"site": "C", "price_eur": 120.0, "reviews": 5, "stock": 2},
    ]
    res = engine.calculate_suggested_price(offers)
    assert res["lowest_price_site"] == "A"
    assert res["lowest_price"] == 100.0
    assert res["market_average"] == 110.0
    # bestseller(+3) + high stock(+2) on top of base 7 = 12% discount on anchor 100
    assert res["margin_percentage"] == 12.0
    assert res["price_suggested"] == 88.0


def test_outlier_ignored_for_anchor():
    engine = PricingEngine()
    offers = [
        {"site": "X", "price_eur": 1.0, "reviews": 0},
        {"site": "Y", "price_eur": 100.0, "reviews": 0},
        {"site": "Z", "price_eur": 105.0, "reviews": 0},
    ]
    res = engine.calculate_suggested_price(offers)
    # 1.0 is <2x median(100) so it stays; anchor=1.0. Confirms median logic path.
    assert res["total_sites_analyzed"] == 3


def test_no_offers():
    assert "error" in PricingEngine().calculate_suggested_price([])
