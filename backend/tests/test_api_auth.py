"""Test per le route /api/auth/*."""

import pytest


def test_signup_success(client):
    resp = client.post('/api/auth/signup', json={
        'email': 'nuovo@example.com',
        'password': 'SecurePass1!',
        'name': 'Mario',
        'surname': 'Rossi',
        'privacy_accepted': True,
        'newsletter_opt_in': False,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert data['user']['email'] == 'nuovo@example.com'


def test_signup_duplicate_email(client, user):
    resp = client.post('/api/auth/signup', json={
        'email': 'test@example.com',
        'password': 'Pass123!',
        'name': 'Luigi',
        'surname': 'Verdi',
        'privacy_accepted': True,
        'newsletter_opt_in': False,
    })
    assert resp.status_code == 400
    assert resp.get_json()['success'] is False


def test_signup_missing_privacy(client):
    resp = client.post('/api/auth/signup', json={
        'email': 'altro@example.com',
        'password': 'Pass123!',
        'name': 'Anna',
        'surname': 'Bianchi',
        'privacy_accepted': False,
        'newsletter_opt_in': False,
    })
    assert resp.status_code == 400
    assert 'privacy' in resp.get_json()['message'].lower()


def test_login_success(client, user):
    resp = client.post('/api/auth/login',
                       json={'email': 'test@example.com', 'password': 'password123'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert 'user' in data


def test_login_wrong_password(client, user):
    resp = client.post('/api/auth/login',
                       json={'email': 'test@example.com', 'password': 'wrong'})
    assert resp.status_code == 401
    assert resp.get_json()['success'] is False


def test_me_unauthenticated(client):
    resp = client.get('/api/auth/me')
    assert resp.status_code == 200
    assert resp.get_json()['authenticated'] is False


def test_me_authenticated(auth_client):
    resp = auth_client.get('/api/auth/me')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['authenticated'] is True
    assert data['user']['email'] == 'test@example.com'
