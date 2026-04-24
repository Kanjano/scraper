"""Test per POST /api/search."""

import pytest
from unittest.mock import patch

FAKE_RESULTS = [
    {
        "nome": "Chitarra Fender Stratocaster",
        "prezzo": "500,00",
        "prezzo_numerico": 500.0,
        "prezzo_originale": "600,00",
        "prezzo_originale_numerico": 600.0,
        "link": "https://thomann.de/fender",
        "immagine": "img1.jpg",
        "sito": "Thomann",
    },
    {
        "nome": "Chitarra Gibson Les Paul",
        "prezzo": "800,00",
        "prezzo_numerico": 800.0,
        "prezzo_originale": "800,00",
        "prezzo_originale_numerico": 800.0,
        "link": "https://gear4music.com/gibson",
        "immagine": "img2.jpg",
        "sito": "Gear4music",
    },
]


def _patch_scrapers(fake_items=None):
    """Restituisce un context manager che mocka run_all_scrapers."""
    items = fake_items if fake_items is not None else FAKE_RESULTS
    return patch('scraper_service.run_all_scrapers', return_value=(list(items), {}))


def test_search_empty_query(client):
    resp = client.post('/api/search', json={'prodotto': '', 'siti': []})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['results'] == []
    assert data['count'] == 0


def test_search_no_json_body(client):
    resp = client.post('/api/search', data='not-json', content_type='text/plain')
    assert resp.status_code == 400


def test_search_returns_json(client):
    with _patch_scrapers([]):
        resp = client.post('/api/search', json={'prodotto': 'chitarra', 'siti': []})
    assert 'application/json' in resp.content_type


def test_search_response_has_required_fields(client):
    with _patch_scrapers(FAKE_RESULTS):
        resp = client.post('/api/search', json={'prodotto': 'chitarra', 'siti': []})
    assert resp.status_code == 200
    data = resp.get_json()
    for field in ('results', 'count', 'stats', 'search_mode', 'normalized_query'):
        assert field in data, f"Campo mancante: {field}"


def test_search_valid_query_returns_results(client):
    with _patch_scrapers(FAKE_RESULTS):
        resp = client.post('/api/search', json={'prodotto': 'Chitarra', 'siti': []})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['count'] > 0
    assert len(data['results']) > 0


def test_search_results_have_sito_field(client):
    with _patch_scrapers(FAKE_RESULTS):
        resp = client.post('/api/search', json={'prodotto': 'chitarra', 'siti': []})
    data = resp.get_json()
    for item in data['results']:
        assert 'sito' in item
