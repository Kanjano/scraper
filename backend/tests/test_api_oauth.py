"""Test per integrazione OAuth (level 3: providers endpoint + redirect flow)."""

import os
import pytest
from urllib.parse import urlparse, parse_qs


# --- /api/auth/oauth/providers ---

def test_oauth_providers_endpoint_status(client):
    resp = client.get('/api/auth/oauth/providers')
    assert resp.status_code == 200


def test_oauth_providers_endpoint_shape(client):
    resp = client.get('/api/auth/oauth/providers')
    data = resp.get_json()
    assert 'providers' in data
    providers = data['providers']
    assert set(providers.keys()) == {'google', 'facebook', 'twitter'}
    for v in providers.values():
        assert isinstance(v, bool)


def test_oauth_providers_google_configured_when_env_set(client):
    """Con GOOGLE_CLIENT_ID + SECRET in .env, google deve risultare True."""
    if not (os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET')):
        pytest.skip("GOOGLE_CLIENT_ID/SECRET non in .env")
    resp = client.get('/api/auth/oauth/providers')
    assert resp.get_json()['providers']['google'] is True


def test_oauth_providers_facebook_not_configured(client):
    """Facebook non in .env → deve risultare False."""
    if os.getenv('FACEBOOK_CLIENT_ID') and os.getenv('FACEBOOK_CLIENT_SECRET'):
        pytest.skip("FACEBOOK creds presenti, test salta")
    resp = client.get('/api/auth/oauth/providers')
    assert resp.get_json()['providers']['facebook'] is False


def test_oauth_providers_twitter_not_configured(client):
    if os.getenv('TWITTER_CLIENT_ID') and os.getenv('TWITTER_CLIENT_SECRET'):
        pytest.skip("TWITTER creds presenti, test salta")
    resp = client.get('/api/auth/oauth/providers')
    assert resp.get_json()['providers']['twitter'] is False


# --- /login/<provider> redirect flow ---

def test_login_google_redirects_to_google(client):
    """Con creds configurate, /login/google deve restituire 302 verso accounts.google.com."""
    if not (os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET')):
        pytest.skip("GOOGLE_CLIENT_ID/SECRET non in .env")

    resp = client.get('/login/google', follow_redirects=False)
    assert resp.status_code == 302

    location = resp.headers.get('Location', '')
    parsed = urlparse(location)
    assert 'google.com' in parsed.netloc, f"Expected google.com in redirect, got: {location}"

    qs = parse_qs(parsed.query)
    assert 'client_id' in qs
    assert qs['client_id'][0] == os.getenv('GOOGLE_CLIENT_ID')
    assert 'redirect_uri' in qs
    assert '/login/google/callback' in qs['redirect_uri'][0]
    assert 'response_type' in qs
    assert qs['response_type'][0] == 'code'
    assert 'scope' in qs
    assert 'openid' in qs['scope'][0]
    assert 'email' in qs['scope'][0]


def test_login_facebook_without_config_redirects_with_error(client, monkeypatch):
    """Provider non configurato → redirect a /login?error=oauth_not_configured&provider=facebook."""
    monkeypatch.delenv('FACEBOOK_CLIENT_ID', raising=False)
    monkeypatch.delenv('FACEBOOK_CLIENT_SECRET', raising=False)

    resp = client.get('/login/facebook', follow_redirects=False)
    assert resp.status_code == 302

    location = resp.headers.get('Location', '')
    parsed = urlparse(location)
    assert parsed.path == '/login'

    qs = parse_qs(parsed.query)
    assert qs.get('error') == ['oauth_not_configured']
    assert qs.get('provider') == ['facebook']


def test_login_unsupported_provider_redirects_with_error(client):
    resp = client.get('/login/myspace', follow_redirects=False)
    assert resp.status_code == 302

    location = resp.headers.get('Location', '')
    parsed = urlparse(location)
    assert parsed.path == '/login'
    qs = parse_qs(parsed.query)
    assert qs.get('error') == ['oauth_unsupported_provider']
    assert qs.get('provider') == ['myspace']


def test_login_google_unconfigured_redirects_with_error(client, monkeypatch):
    """Google senza creds → redirect con error=oauth_not_configured."""
    monkeypatch.delenv('GOOGLE_CLIENT_ID', raising=False)
    monkeypatch.delenv('GOOGLE_CLIENT_SECRET', raising=False)

    resp = client.get('/login/google', follow_redirects=False)
    assert resp.status_code == 302

    location = resp.headers.get('Location', '')
    parsed = urlparse(location)
    assert parsed.path == '/login'
    qs = parse_qs(parsed.query)
    assert qs.get('error') == ['oauth_not_configured']
    assert qs.get('provider') == ['google']


# --- /login/<provider>/callback (errori) ---

def test_callback_unsupported_provider(client):
    resp = client.get('/login/myspace/callback', follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers.get('Location', '')
    parsed = urlparse(location)
    qs = parse_qs(parsed.query)
    assert qs.get('error') == ['oauth_unsupported_provider']


def test_callback_without_state_returns_error(client):
    """Callback senza state/code → eccezione catturata, redirect con error."""
    if not (os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET')):
        pytest.skip("GOOGLE_CLIENT_ID/SECRET non in .env")

    resp = client.get('/login/google/callback', follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers.get('Location', '')
    parsed = urlparse(location)
    assert parsed.path == '/login'
    qs = parse_qs(parsed.query)
    assert qs.get('error') == ['oauth_callback_error']
