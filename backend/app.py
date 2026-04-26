import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module='urllib3')

import logging
from flask import Flask, request, session, g, jsonify, send_from_directory, redirect, url_for
import smtplib
import os
import json
from urllib.parse import urlencode
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from flask_cors import CORS
from models import db, User, SearchHistory
from authlib.integrations.flask_client import OAuth

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger('auth')

OAUTH_PROVIDERS = ('google', 'facebook', 'twitter')


def _provider_configured(provider: str) -> bool:
    return bool(
        os.getenv(f'{provider.upper()}_CLIENT_ID')
        and os.getenv(f'{provider.upper()}_CLIENT_SECRET')
    )


def _login_redirect(error_code: str, provider: str | None = None):
    params = {'error': error_code}
    if provider:
        params['provider'] = provider
    return redirect(f'/login?{urlencode(params)}')

from scraper_service import (
    run_all_scrapers, filter_and_rank_results,
    calculate_discounts, apply_referral_links, get_top_discounts,
)
from search_normalizer import normalize_query, find_similar_queries
from referral_db_manager import ReferralDBManager

load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

_secret = os.environ.get('SECRET_KEY')
if not _secret:
    print("WARNING: SECRET_KEY non impostata — uso chiave di fallback. NON adatto alla produzione.")
    _secret = 'dev-fallback-non-sicuro'
app.secret_key = _secret

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///scraper.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


# --- SPA catch-all ---
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path and os.path.exists(os.path.join(app.static_folder or '', path)):
        return send_from_directory(app.static_folder, path)
    if path.startswith('api/'):
        return jsonify({'error': 'Endpoint non trovato'}), 404
    return send_from_directory(app.static_folder, 'index.html')


db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

oauth = OAuth(app)
oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)
oauth.register(
    name='facebook',
    client_id=os.getenv('FACEBOOK_CLIENT_ID'),
    client_secret=os.getenv('FACEBOOK_CLIENT_SECRET'),
    access_token_url='https://graph.facebook.com/oauth/access_token',
    authorize_url='https://www.facebook.com/dialog/oauth',
    api_base_url='https://graph.facebook.com/',
    client_kwargs={'scope': 'email'},
)
oauth.register(
    name='twitter',
    client_id=os.getenv('TWITTER_CLIENT_ID'),
    client_secret=os.getenv('TWITTER_CLIENT_SECRET'),
    api_base_url='https://api.twitter.com/2/',
    request_token_url='https://api.twitter.com/oauth/request_token',
    access_token_url='https://api.twitter.com/oauth/access_token',
    authorize_url='https://api.twitter.com/oauth/authenticate',
    client_kwargs=None,
)

for _p in OAUTH_PROVIDERS:
    if _provider_configured(_p):
        logger.info(f"OAuth provider '{_p}' configurato.")
    else:
        logger.warning(
            f"OAuth provider '{_p}' NON configurato: imposta "
            f"{_p.upper()}_CLIENT_ID e {_p.upper()}_CLIENT_SECRET in .env"
        )


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


ReferralDBManager.log_referral_status()

try:
    from translations import get_locale, get_translations, get_available_languages
except ImportError:
    def get_locale(): return 'en'
    def get_translations(lang=None): return {}
    def get_available_languages(): return {'en': 'English'}


@app.context_processor
def inject_translations():
    translations = get_translations()
    def translate(key, **kwargs):
        return translations.get(key, key).format(**kwargs)
    return dict(_=translate)


@app.before_request
def before_request():
    if 'lang' not in session:
        session['lang'] = get_locale()
    g.current_lang = session['lang']
    g.available_languages = get_available_languages()


@app.route('/set_language/<lang>')
def set_language(lang):
    if lang in get_available_languages():
        session['lang'] = lang
    return redirect(request.referrer or '/')


# --- OAuth routes ---

@app.route('/login/<provider>')
def login_oauth(provider):
    if provider not in OAUTH_PROVIDERS:
        logger.warning(f"OAuth: provider '{provider}' non supportato.")
        return _login_redirect('oauth_unsupported_provider', provider)

    if not _provider_configured(provider):
        logger.error(
            f"OAuth: tentativo login con '{provider}' ma credenziali mancanti "
            f"({provider.upper()}_CLIENT_ID/SECRET non in .env)."
        )
        return _login_redirect('oauth_not_configured', provider)

    client = oauth.create_client(provider)
    if not client:
        logger.error(f"OAuth: create_client('{provider}') ha restituito None.")
        return _login_redirect('oauth_client_init_failed', provider)

    callback_url = url_for('authorize_oauth', provider=provider, _external=True)
    logger.info(f"OAuth: avvio flow '{provider}', callback={callback_url}")
    try:
        return client.authorize_redirect(callback_url)
    except Exception as e:
        logger.exception(f"OAuth: errore in authorize_redirect per '{provider}': {e}")
        return _login_redirect('oauth_redirect_failed', provider)


@app.route('/login/<provider>/callback')
def authorize_oauth(provider):
    if provider not in OAUTH_PROVIDERS:
        logger.warning(f"OAuth callback: provider '{provider}' non supportato.")
        return _login_redirect('oauth_unsupported_provider', provider)

    client = oauth.create_client(provider)
    if not client:
        logger.error(f"OAuth callback: create_client('{provider}') ha restituito None.")
        return _login_redirect('oauth_client_init_failed', provider)

    try:
        token = client.authorize_access_token()
        logger.info(f"OAuth callback '{provider}': token ricevuto.")

        if provider == 'google':
            info = token.get('userinfo')
            if not info:
                info = client.get('https://openidconnect.googleapis.com/v1/userinfo').json()
            email, name, surname, oauth_id = (
                info.get('email'), info.get('given_name'),
                info.get('family_name'), info.get('sub') or info.get('id'),
            )
        elif provider == 'facebook':
            info = client.get('me?fields=id,name,email,first_name,last_name').json()
            email, name, surname, oauth_id = (
                info.get('email'), info.get('first_name'),
                info.get('last_name'), info.get('id'),
            )
        elif provider == 'twitter':
            info = client.get('account/verify_credentials.json?include_email=true').json()
            parts = (info.get('name') or 'Twitter User').split(' ', 1)
            email = info.get('email')
            name, surname = parts[0], parts[1] if len(parts) > 1 else 'User'
            oauth_id = str(info.get('id'))
        else:
            logger.error(f"OAuth callback: provider '{provider}' non gestito.")
            return _login_redirect('oauth_unhandled_provider', provider)

        if not email:
            logger.error(f"OAuth callback '{provider}': nessuna email da provider. info={info!r}")
            return _login_redirect('oauth_no_email', provider)

        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email, name=name, surname=surname,
                        oauth_provider=provider, oauth_id=oauth_id,
                        privacy_accepted=True, newsletter_opt_in=False)
            db.session.add(user)
            db.session.commit()
            logger.info(f"OAuth: nuovo utente creato '{email}' via {provider}.")
        elif not user.oauth_provider:
            user.oauth_provider = provider
            user.oauth_id = oauth_id
            db.session.commit()
            logger.info(f"OAuth: utente esistente '{email}' collegato a {provider}.")
        else:
            logger.info(f"OAuth: login utente '{email}' via {provider}.")

        login_user(user)
        return redirect('/')
    except Exception as e:
        logger.exception(f"OAuth callback '{provider}': errore: {e}")
        return _login_redirect('oauth_callback_error', provider)


@app.route('/api/auth/oauth/providers', methods=['GET'])
def api_oauth_providers():
    """Restituisce providers OAuth configurati (frontend nasconde quelli non disponibili)."""
    return jsonify({
        'providers': {p: _provider_configured(p) for p in OAUTH_PROVIDERS}
    }), 200


# --- API ---

@app.route('/api/auth/me', methods=['GET'])
def api_me():
    if current_user.is_authenticated:
        return jsonify({
            "authenticated": True,
            "user": {
                "id": current_user.id, "email": current_user.email,
                "name": current_user.name, "surname": current_user.surname,
            },
        })
    return jsonify({"authenticated": False}), 200


@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    user = User.query.filter_by(email=data.get('email')).first()
    if user and user.check_password(data.get('password', '')):
        login_user(user)
        return jsonify({"success": True, "user": {"email": user.email, "name": user.name}}), 200
    return jsonify({"success": False, "message": "Email o password non validi"}), 401


@app.route('/api/auth/logout', methods=['POST'])
@login_required
def api_logout():
    logout_user()
    return jsonify({"success": True}), 200


@app.route('/api/auth/signup', methods=['POST'])
def api_signup():
    data = request.get_json() or {}
    if not data.get('privacy_accepted'):
        return jsonify({"success": False, "message": "Devi accettare la privacy policy"}), 400
    if User.query.filter_by(email=data.get('email')).first():
        return jsonify({"success": False, "message": "Email già registrata"}), 400
    user = User(
        email=data['email'], name=data.get('name'), surname=data.get('surname'),
        privacy_accepted=True, newsletter_opt_in=data.get('newsletter_opt_in', False),
    )
    user.set_password(data.get('password', ''))
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return jsonify({"success": True, "user": {"email": data['email'], "name": data.get('name')}}), 200


@app.route('/api/search', methods=['POST'])
def api_search():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Nessun dato JSON fornito"}), 400

        raw_query = data.get('prodotto', '').strip()
        sites = data.get('siti', [])
        if isinstance(sites, str):
            sites = [s.strip() for s in sites.split(',') if s.strip()]

        if not raw_query:
            return jsonify({"results": [], "count": 0, "message": "Query non fornita"}), 200

        norm_query = normalize_query(raw_query)

        if current_user.is_authenticated:
            try:
                last = (SearchHistory.query
                        .filter_by(user_id=current_user.id)
                        .order_by(SearchHistory.timestamp.desc())
                        .first())
                if not last or last.search_term != raw_query:
                    db.session.add(SearchHistory(
                        user_id=current_user.id,
                        search_term=raw_query,
                        filters=json.dumps(data),
                    ))
                    db.session.commit()
            except Exception as e:
                print(f"Errore salvataggio storico: {e}")

        results, stats = run_all_scrapers(norm_query, sites)
        results = calculate_discounts(results)
        results = apply_referral_links(results, ReferralDBManager)
        ranked, search_mode = filter_and_rank_results(results, norm_query)
        top_discounts = get_top_discounts(ranked)

        return jsonify({
            "results": ranked,
            "stats": stats,
            "top_discounts": top_discounts,
            "search_mode": search_mode,
            "count": len(ranked),
            "normalized_query": norm_query,
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/search/suggestions', methods=['POST'])
def api_suggestions():
    data = request.get_json() or {}
    raw = data.get('query', '').strip()
    if not raw:
        return jsonify({"suggestions": [], "normalized_query": ""}), 200

    norm = normalize_query(raw)
    history = [
        h.search_term
        for h in SearchHistory.query.order_by(SearchHistory.timestamp.desc()).limit(200).all()
    ]
    suggestions = find_similar_queries(norm, history, limit=5)
    return jsonify({"suggestions": suggestions, "normalized_query": norm}), 200


@app.route('/api/contacts', methods=['POST'])
def api_contacts():
    data = request.get_json() or {}
    nome = data.get('nome')
    email = data.get('email')
    messaggio = data.get('message') or data.get('messaggio')

    if not nome or not email or not messaggio:
        return jsonify({'success': False, 'message': 'Tutti i campi sono obbligatori.'}), 400

    try:
        msg = MIMEMultipart()
        msg['From'] = os.getenv('EMAIL_SENDER')
        msg['To'] = "antonio.web2music@gmail.com"
        msg['Subject'] = f'Nuovo messaggio da {nome} (via API)'
        msg.attach(MIMEText(f"Nome: {nome}\nEmail: {email}\nMessaggio:\n{messaggio}", 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(os.getenv('EMAIL_SENDER'), os.getenv('EMAIL_PASSWORD'))
        server.sendmail(msg['From'], msg['To'], msg.as_string())
        server.quit()
        return jsonify({'success': True, 'message': 'Messaggio inviato con successo!'}), 200
    except Exception as e:
        print(f"Errore invio email: {e}")
        return jsonify({'success': False, 'message': "Errore durante l'invio del messaggio."}), 500


@app.cli.command("send-newsletter")
def send_newsletter_command():
    from newsletter_manager import send_weekly_newsletter
    send_weekly_newsletter()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
