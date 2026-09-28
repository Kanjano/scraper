"""Schema.org and repeated-grid extraction, the two generic parsers."""
from scrapers.grid import heuristic_products
from scrapers.structured import extract_products

JSONLD = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"ItemList","itemListElement":[
 {"@type":"Product","name":"Fender Stratocaster","brand":{"@type":"Brand","name":"Fender"},
  "sku":"STRAT1","url":"/p/strat",
  "offers":{"@type":"Offer","price":"1299.00","priceCurrency":"EUR",
            "availability":"https://schema.org/InStock"}},
 {"@type":"Product","name":"Gibson Les Paul","url":"/p/lp",
  "offers":{"@type":"AggregateOffer","lowPrice":"2499.50","priceCurrency":"EUR"}}
]}
</script></head><body></body></html>
"""

MICRODATA = """
<html><body>
<div itemscope itemtype="http://schema.org/Product">
  <span itemprop="name">Yamaha P-45</span>
  <meta itemprop="price" content="499.00">
  <meta itemprop="priceCurrency" content="EUR">
  <a itemprop="url" href="/p/p45">detail</a>
</div></body></html>
"""

GRID = """
<html><body>
<header><a href="/cart">Cart</a><span>Free shipping over $99</span></header>
<ul class="results">
  <li class="card"><a href="/p/1"><img alt="Ludwig Supraphonic Snare 14x6.5"></a>
      <h3>Ludwig Supraphonic Snare 14x6.5</h3><span class="price">$649.95</span></li>
  <li class="card"><a href="/p/2"><h3>Zildjian K Custom Dark Ride 22"</h3>
      <span class="price money">$489.00</span>
      <span class="compare-at">$599.00</span></li>
  <li class="card"><a href="/p/3"><h3>Gretsch Catalina Maple Shell Pack</h3>
      <span class="price">$1,099.00</span>
      <span class="financing">as low as $44/mo</span></li>
</ul></body></html>
"""


def test_jsonld_products():
    recs = extract_products(JSONLD)
    assert [r["name"] for r in recs] == ["Fender Stratocaster", "Gibson Les Paul"]
    first = recs[0]
    assert first["price"] == 1299.0
    assert first["currency"] == "EUR"
    assert first["brand"] == "Fender"
    assert first["external_id"] == "STRAT1"
    assert first["stock"] == 1
    assert recs[1]["price"] == 2499.5  # AggregateOffer lowPrice


def test_microdata_fallback():
    recs = extract_products(MICRODATA)
    assert len(recs) == 1
    assert recs[0]["name"] == "Yamaha P-45"
    assert recs[0]["price"] == 499.0


def test_grid_detection_ignores_chrome_and_financing():
    recs = heuristic_products(GRID)
    names = [r["name"] for r in recs]
    assert len(recs) == 3, names
    by_name = {r["name"]: r for r in recs}
    assert by_name["Ludwig Supraphonic Snare 14x6.5"]["price"] == 649.95
    # sale price wins over the struck-through one
    assert by_name['Zildjian K Custom Dark Ride 22"']["price"] == 489.0
    # instalment price must not be mistaken for the product price
    assert by_name["Gretsch Catalina Maple Shell Pack"]["price"] == 1099.0
    assert by_name["Ludwig Supraphonic Snare 14x6.5"]["url"] == "/p/1"


def test_grid_returns_nothing_without_a_grid():
    assert heuristic_products("<html><body><p>No products here</p></body></html>") == []


INLINE_JSON = """
<html><head>
<script type="application/json" id="__NEXT_DATA__">
{"props":{"pageProps":{"results":{"items":[
  {"id":"a1","title":"1959 Gibson ES-225 TDN","price":11200,"currency":"USD",
   "brand":"Gibson","slug":"/p/es225"},
  {"id":"a2","title":"1982 Fender Stratocaster Left Hand","price":"3,500.00",
   "currency":"USD"},
  {"id":"nav","title":"Contact","price":0}
]}}}}
</script></head><body></body></html>
"""


def test_inline_json_products():
    from scrapers.inline_json import products_from_inline_json

    recs = products_from_inline_json(INLINE_JSON)
    assert [r["name"] for r in recs] == [
        "1959 Gibson ES-225 TDN",
        "1982 Fender Stratocaster Left Hand",
    ]
    assert recs[0]["price"] == 11200.0
    assert recs[0]["currency"] == "USD"
    assert recs[0]["brand"] == "Gibson"
    assert recs[0]["url"] == "/p/es225"
    assert recs[1]["price"] == 3500.0  # localized string parsed


def test_extract_any_prefers_schema_org_then_json_then_grid():
    from scrapers.structured import extract_any

    assert extract_any(JSONLD)[1] == "structured"
    assert extract_any(INLINE_JSON)[1] == "inline_json"
    assert extract_any(GRID)[1] == "heuristic"
    assert extract_any("<html><body>nothing</body></html>") == ([], None)


def test_grid_ignores_monthly_instalments_and_joins_split_prices():
    card = """
    <li class="product"><a href="/p/{i}"><h3>Yamaha MONTAGE M8x Synth {i}</h3></a>
      <span class="fancy-price"><span>$</span><span class="price">4,699 </span><span> .99</span></span>
      <div class="finance"><span>or</span> <span class="ala-price">$392.00</span><span>/month</span></div>
      <p><span>€ 35,00</span> <span>al mese</span></p>
    </li>"""
    html = "<ul>" + "".join(card.format(i=i) for i in range(4)) + "</ul>"
    records = heuristic_products(html)
    assert records and {r["price"] for r in records} == {4699.99}
