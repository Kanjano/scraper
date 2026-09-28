from scrapers.parsers import parse_price


def test_eu_format():
    assert parse_price("1.299,99 €") == 1299.99


def test_us_format():
    assert parse_price("$1,299.99") == 1299.99


def test_plain():
    assert parse_price("129.99") == 129.99


def test_comma_decimal():
    assert parse_price("129,99") == 129.99


def test_none():
    assert parse_price("no price") is None
    assert parse_price(None) is None


def test_eu_thousands_without_decimals():
    # "4.270 ₺" is 4270, not 4.27 (de/it/tr/es grouping).
    assert parse_price("4.270 ₺") == 4270.0
    assert parse_price("1.299") == 1299.0


def test_us_thousands_without_decimals():
    assert parse_price("$1,299") == 1299.0


def test_two_decimals_kept():
    assert parse_price("129.99") == 129.99
    assert parse_price("1.299,00 €") == 1299.0


def test_space_thousands_separator():
    # Forks Drum Closet renders "$3 199.00"; fr/ch shops use "1 299,00 €".
    assert parse_price("$3 199.00") == 3199.0
    assert parse_price("1 299,00 €") == 1299.0
    assert parse_price("12 345 678,90") == 12345678.9
    # A space that is not a thousands group must not glue numbers together.
    assert parse_price("Pack 3 x 12,50 €") == 3.0
