"""Fixtures condivise per i test del backend."""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def app():
    # Patch i moduli Selenium/scraper prima di importare app
    scraper_patches = [
        'scraper_centrochitarre.cerca_centrochitarre',
        'scraper_tomassone.cerca_tomassone',
        'scraper_musik_produktiv.cerca_musik_produktiv',
        'scraper_thomann.cerca_thomann',
        'scraper_andertons.cerca_andertons',
        'scraper_gear4music.cerca_gear4music',
        'scraper_strumentimusicali.search_strumentimusicali',
    ]

    # Patch browser manager per evitare Selenium reale
    browser_patch = patch('browser_manager.BrowserManager.create_driver', return_value=MagicMock())
    referral_patch = patch('referral_db_manager.ReferralDBManager.log_referral_status')
    referral_get_patch = patch(
        'referral_db_manager.ReferralDBManager.get_referral_link',
        side_effect=lambda link: link
    )

    with browser_patch, referral_patch, referral_get_patch:
        import app as flask_app

        flask_app.app.config.update({
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'WTF_CSRF_ENABLED': False,
            'SECRET_KEY': 'test-secret',
            'LOGIN_DISABLED': False,
        })

        with flask_app.app.app_context():
            flask_app.db.create_all()
            yield flask_app.app
            flask_app.db.session.remove()
            flask_app.db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    import app as flask_app
    return flask_app.db


@pytest.fixture
def user(db, app):
    import app as flask_app
    from models import User
    with app.app_context():
        u = User(email='test@example.com', name='Test', surname='User',
                 privacy_accepted=True, newsletter_opt_in=False)
        u.set_password('password123')
        flask_app.db.session.add(u)
        flask_app.db.session.commit()
        return u


@pytest.fixture
def auth_client(client, user):
    client.post('/api/auth/login',
                json={'email': 'test@example.com', 'password': 'password123'},
                content_type='application/json')
    return client
