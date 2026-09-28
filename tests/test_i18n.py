"""Page language from the visitor's country, across every continent."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import i18n
from api.main import app
from config.settings import settings

HTML = {"accept": "text/html"}

# country -> expected language, one row per continent and per major language.
BY_COUNTRY = {
    # Europe
    "IT": "it", "DE": "de", "FR": "fr", "ES": "es", "GB": "en", "RU": "ru", "TR": "tr",
    "AT": "de", "PT": "pt", "CH": "de", "BE": "fr",  # BE: nl first, unsupported -> fr
    # Americas
    "US": "en", "MX": "es", "CA": "en", "BR": "pt", "AR": "es", "CO": "es",
    # Africa
    "EG": "ar", "MA": "ar", "NG": "en", "KE": "sw", "TZ": "sw", "ZA": "en", "SN": "fr",
    # Asia
    "CN": "zh", "TW": "zh_Hant", "HK": "zh_Hant", "JP": "ja", "KR": "ko", "IN": "hi",
    "PK": "ur", "BD": "bn", "ID": "id", "SA": "ar", "AE": "ar",
    # Oceania
    "AU": "en", "NZ": "en",
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _page(client, **headers):
    client.cookies.clear()  # a ?lang= choice from another test would win
    r = client.get("/", headers={**HTML, **headers})
    assert r.status_code == 200
    return r


@pytest.mark.parametrize("country,lang", BY_COUNTRY.items())
def test_language_follows_country(client, country, lang):
    r = _page(client, **{"cf-ipcountry": country})
    assert r.headers["content-language"] == lang.replace("_", "-")
    title = i18n.TRANSLATIONS[lang]["title"]
    assert f"<title>INSTRINDER — {title.replace(chr(39), '&#x27;')}</title>" in r.text


def test_browser_language_breaks_ties_in_multilingual_countries(client):
    assert _page(client, **{"cf-ipcountry": "CH", "accept-language": "fr-CH,fr;q=0.9"}) \
        .headers["content-language"] == "fr"
    assert _page(client, **{"cf-ipcountry": "IN", "accept-language": "en-IN,en;q=0.8"}) \
        .headers["content-language"] == "en"
    # A language not spoken in that country does not override it.
    assert _page(client, **{"cf-ipcountry": "JP", "accept-language": "de"}) \
        .headers["content-language"] == "ja"


def test_fallbacks(client):
    # Country without a supported language -> browser language -> English.
    assert _page(client, **{"cf-ipcountry": "NL", "accept-language": "nl,de;q=0.5"}) \
        .headers["content-language"] == "de"
    assert _page(client, **{"cf-ipcountry": "NL"}).headers["content-language"] == "en"
    assert _page(client, **{"accept-language": "pt-BR"}).headers["content-language"] == "pt"


def test_explicit_choice_wins_and_sticks(client):
    r = client.get("/?lang=ja", headers={**HTML, "cf-ipcountry": "IT"})
    assert r.headers["content-language"] == "ja"
    assert "lang=ja" in r.headers["set-cookie"]
    r = client.get("/", headers={**HTML, "cf-ipcountry": "IT", "cookie": "lang=ko"})
    assert r.headers["content-language"] == "ko"


@pytest.mark.parametrize("lang", ["ar", "ur"])
def test_right_to_left_scripts(client, lang):
    r = client.get(f"/?lang={lang}", headers=HTML)
    assert re.search(r'<html lang="\w+" dir="rtl">', r.text)


def test_api_clients_still_get_json(client):
    assert client.get("/").json()["service"] == "strumenti-musicali-scraper"


def test_every_language_renders_complete(client):
    for lang in i18n.SUPPORTED:
        r = client.get(f"/?lang={lang}", headers=HTML)
        assert "$" not in r.text.split("<script>")[0], lang  # no unfilled placeholder
        assert i18n.TRANSLATIONS[lang]["search"] in r.text


@pytest.mark.skipif(not Path(settings.geoip_db).exists(), reason="GeoIP database not downloaded")
def test_geoip_from_client_ip(client):
    assert _page(client, **{"x-forwarded-for": "8.8.8.8"}).headers["x-visitor-country"] == "US"
    # Private addresses carry no country: falls back to the browser.
    r = _page(client, **{"x-forwarded-for": "192.168.1.10", "accept-language": "es"})
    assert r.headers["content-language"] == "es"
