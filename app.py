import warnings
# Disabilita tutti gli avvisi di urllib3
warnings.filterwarnings("ignore", category=DeprecationWarning, module='urllib3')

from flask import Flask, render_template, request, redirect, flash, session, url_for, g
import geocoder
import requests
import smtplib
import time
import os
import re
import difflib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from difflib import SequenceMatcher

# Importa il gestore della cache
from cache_manager import cleanup_cache, cleanup_on_error
# Importa il gestore dei referral link basato su database
from referral_db_manager import ReferralDBManager
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from models import db, User, SearchHistory
from authlib.integrations.flask_client import OAuth

def get_country_from_ip(ip_address: str) -> str:
    """Ottiene il codice paese dall'indirizzo IP usando ipapi.co"""
    print(f"\n=== DEBUG GEOCODING ===")
    print(f"Indirizzo IP da analizzare: {ip_address}")
    
    try:
        url = f'https://ipapi.co/{ip_address}/country/'
        print(f"Richiesta a: {url}")
        
        response = requests.get(url, timeout=5)  # Timeout di 5 secondi
        print(f"Stato risposta: {response.status_code}")
        
        if response.status_code == 200:
            country = response.text.strip().upper() or 'IT'
            print(f"Paese rilevato: {country}")
            return country
            
    except requests.exceptions.RequestException as e:
        print(f"Errore durante la richiesta a ipapi.co: {e}")
    except Exception as e:
        print(f"Errore imprevisto durante la geolocalizzazione: {e}")
        
    print("Utilizzo del paese predefinito: IT")
    return 'IT'  # Fallback a Italia

def similar(a: str, b: str) -> float:
    """Calcola la similarità tra due stringhe (0-1)"""
    return SequenceMatcher(None, a, b).ratio()

def filtra_risultati(risultati: list, query: str = "", soglia_similarita: float = 0.6) -> list:
    """
    Restituisce i risultati ordinati per prezzo crescente.
    
    Args:
        risultati: Lista di dizionari contenenti i risultati
        query: Stringa di ricerca (opzionale, non utilizzata)
        soglia_similarita: Parametro mantenuto per compatibilità (non utilizzato)
        
    Returns:
        Lista ordinata per prezzo crescente
    """
    if not risultati:
        return []
    
    def extract_price(item):
        try:
            # Estrae il prezzo dall'item
            price_str = item.get('prezzo', '')
            # Rimuove punti, spazi, € e converte la virgola in punto
            price_str = str(price_str).replace('€', '').replace('.', '').replace(',', '.').strip()
            return float(price_str) if price_str else 999999
        except (ValueError, AttributeError):
            return 999999
    
    # Ordina i risultati per prezzo crescente
    return sorted(risultati, key=lambda x: extract_price(x.get('prezzo')))

from scraper_centrochitarre import cerca_centrochitarre
from scraper_tomassone import cerca_tomassone
from scraper_musik_produktiv import cerca_musik_produktiv
from scraper_thomann import cerca_thomann
from scraper_andertons import cerca_andertons
from scraper_gear4music import cerca_gear4music
from scraper_strumentimusicali import search_strumentimusicali as cerca_strumentimusicali

load_dotenv()

app = Flask(__name__)
app.secret_key = 'supersegreto'

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///scraper.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# OAuth Configuration
oauth = OAuth(app)

# Google
oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={'scope': 'openid email profile'},
)

# Facebook
oauth.register(
    name='facebook',
    client_id=os.getenv('FACEBOOK_CLIENT_ID'),
    client_secret=os.getenv('FACEBOOK_CLIENT_SECRET'),
    access_token_url='https://graph.facebook.com/oauth/access_token',
    access_token_params=None,
    authorize_url='https://www.facebook.com/dialog/oauth',
    authorize_params=None,
    api_base_url='https://graph.facebook.com/',
    client_kwargs={'scope': 'email'},
)

# Twitter (X)
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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Inizializza e registra lo stato del sistema di referral basato su database
from referral_db_manager import ReferralDBManager
ReferralDBManager.log_referral_status()

# Import translations after app is created
try:
    from translations import get_locale, get_translations, get_available_languages
except ImportError:
    # Fallback in case translations are not available
    def get_locale():
        return 'en'
    
    def get_translations(lang=None):
        return {}
    
    def get_available_languages():
        return {'en': 'English'}

# Add context processor to make translations available in all templates
@app.context_processor
def inject_translations():
    translations = get_translations()
    def translate(key, **kwargs):
        return translations.get(key, key).format(**kwargs)
    return dict(_=translate)

# Before request handler to set language
@app.before_request
def before_request():
    if 'lang' not in session:
        session['lang'] = get_locale()
    g.current_lang = session['lang']
    g.available_languages = get_available_languages()

# Route to change language
@app.route('/set_language/<lang>')
def set_language(lang):
    if lang in get_available_languages():
        session['lang'] = lang
    return redirect(request.referrer or url_for('index'))

# -- Utility fuzzy match per il filtro titolo --
def parole_rilevanti(testo):
    # Assicurati che testo sia una stringa
    if not isinstance(testo, str):
        if isinstance(testo, dict):
            # Se è un dizionario, prova a convertirlo in stringa
            testo = str(testo)
        else:
            # Altrimenti restituisci una lista vuota
            return []
            
    stopwords = {"il", "lo", "la", "i", "gli", "le", "di", "a", "da", "in", "su", "con", "per", "tra", "fra", "e"}
    try:
        parole = re.findall(r'\b\w+\b', testo.lower())
        return [p for p in parole if p not in stopwords and len(p) > 1]  # Filtra anche le parole troppo corte
    except Exception as e:
        print(f"⚠️ Errore nell'elaborazione del testo '{testo}': {str(e)}")
        return []

def match_fuzzy(nome, parole_chiave):
    nome_words = parole_rilevanti(nome)
    matched = 0

    for parola in parole_chiave:
        best_match = difflib.get_close_matches(parola, nome_words, n=1, cutoff=0.7)
        if best_match:
            matched += 1

    return matched >= max(1, len(parole_chiave) - 1)

@app.route('/')
def index():
    return render_template('index.html', current_lang=session.get('lang', 'en'))

def sito_attivo(siti_selezionati, nome):
    """
    Verifica se un sito è attivo in base ai siti selezionati dall'utente.
    
    Args:
        siti_selezionati (list): Lista dei siti selezionati dall'utente
        nome (str): Nome del sito da verificare
        
    Returns:
        bool: True se il sito è attivo, False altrimenti
    """
    # Mappa i nomi degli scraper ai valori del form
    mappa_nomi = {
        'thomann': 'Thomann',
        'musik_produktiv': 'Musik Produktiv',
        'gear4music': 'Gear4music',
        'andertons': 'Andertons',
        'centrochitarre': 'Centro Chitarre',
        'tomassone': 'Tomassone',
        'strumentimusicali': 'Strumenti Musicali'
    }
    
    # Se nessun sito è selezionato, considera tutti attivi
    if not siti_selezionati:
        return True
        
    # Cerca il nome corrispondente nella mappa
    for key, value in mappa_nomi.items():
        if value in siti_selezionati and key == nome:
            return True
    return False

def scraping_italia(prodotto, siti_selezionati):
    """
    Esegue lo scraping dei siti italiani in parallelo.
    
    Args:
        prodotto (str): Prodotto da cercare
        siti_selezionati (list): Lista dei siti selezionati dall'utente
        
    Returns:
        dict: Dizionario con i risultati degli scraper italiani
    """
    print("\n🚀 Avvio scraping siti italiani...")
    inizio = time.time()
    
    italia_scrapers = {
        "centrochitarre": ("Centro Chitarre", cerca_centrochitarre),
        "tomassone": ("Tomassone", cerca_tomassone),
    }

    local_risultati = {}
    
    # Filtra solo gli scraper attivi
    scraper_attivi = {
        key: value for key, value in italia_scrapers.items() 
        if sito_attivo(siti_selezionati, key)
    }
    
    if not scraper_attivi:
        print("ℹ️ Nessuno scraper italiano attivo")
        return {}
        
    print(f"🔍 Scraper italiani attivi: {', '.join([v[0] for v in scraper_attivi.values()])}")
    
    with ThreadPoolExecutor(max_workers=len(scraper_attivi)) as pool:
        future_to_site = {}
        
        # Invia i lavori al thread pool
        for key, (nome, scraper) in scraper_attivi.items():
            future = pool.submit(scraper, prodotto)
            future_to_site[future] = (key, nome)
        
        # Elabora i risultati
        for future in as_completed(future_to_site):
            key, nome = future_to_site[future]
            tempo_inizio = time.time()
            
            try:
                risultato = future.result()
                tempo_impiegato = time.time() - tempo_inizio
                
                if not isinstance(risultato, list):
                    print(f"⚠️ {nome}: risultato non valido (atteso lista, ottenuto {type(risultato)})")
                    risultato = []
                
                # Aggiungi il sito a ogni risultato
                for r in risultato:
                    if isinstance(r, dict):
                        r['sito'] = nome
                
                local_risultati[key] = risultato
                
                print(f"✅ {nome}: completato in {tempo_impiegato:.2f}s - Trovati {len(risultato)} risultati")
                
            except Exception as e:
                tempo_impiegato = time.time() - tempo_inizio
                errore = str(e)[:200]
                print(f"❌ {nome}: errore dopo {tempo_impiegato:.2f}s - {errore}")
                local_risultati[key] = []
    
    print(f"🏁 Scraping siti italiani completato in {time.time() - inizio:.2f} secondi")
    return local_risultati

def run_scraper(nome, funzione, *args):
    """
    Esegue una funzione di scraping e registra le statistiche.
    
    Args:
        nome (str): Nome del sito da analizzare
        funzione (callable): Funzione di scraping da eseguire
        *args: Argomenti da passare alla funzione di scraping
        
    Returns:
        list: Lista dei risultati dello scraping
    """
    print(f"\nAvvio scraping {nome}...")
    
    inizio = time.time()
    risultato = []
    errore = None
    
    try:
        # Verifica se è necessario pulire la cache prima dell'esecuzione
        cleanup_cache()
        
        # Esegui lo scraper
        risultato = funzione(*args)
        if not isinstance(risultato, list):
            risultato = []
    except Exception as e:
        errore = str(e)
        print(f" {nome}: errore dopo {time.time() - inizio:.2f}s - {errore[:200]}")
        
        # Pulisci la cache se l'errore è correlato al driver
        if cleanup_on_error(errore):
            print(f"✅ Cache pulita dopo errore in {nome}")
            # Prova a eseguire nuovamente lo scraper dopo la pulizia della cache
            try:
                print(f"🔄 Nuovo tentativo per {nome} dopo pulizia cache...")
                risultato = funzione(*args)
                if not isinstance(risultato, list):
                    risultato = []
                errore = None  # Resetta l'errore se il secondo tentativo ha successo
            except Exception as e2:
                errore = f"Anche dopo la pulizia della cache: {str(e2)}"
                print(f"❌ {nome}: errore anche dopo pulizia cache - {errore[:200]}")
                risultato = []
        else:
            risultato = []
    
    # Calcola le statistiche
    tempo_impiegato = time.time() - inizio
    num_oggetti = len(risultato) if isinstance(risultato, list) else 0
    
    # Registra le statistiche
    stats = {
        'tempo': tempo_impiegato,
        'oggetti': num_oggetti,
        'stato': 'completato' if errore is None else 'errore',
    }
    
    if errore:
        stats['errore'] = errore
    
    print(f"{nome}: completato in {tempo_impiegato:.2f}s")
    print(f"   Trovati {num_oggetti} risultati")
    if num_oggetti > 0 and isinstance(risultato, list):
        # Mostra i nomi dei prodotti nei log (cerca in diverse chiavi possibili)
        primi_risultati = []
        for r in risultato[:3]:
            nome_prodotto = r.get('nome') or r.get('titolo') or r.get('name') or 'N/A'
            primi_risultati.append(f"{nome_prodotto[:50]}... - €{r.get('prezzo', 'N/A')}")
        print(f"   Primi 3 risultati: {primi_risultati}")

    return risultato

@app.route('/search', methods=['GET', 'POST'])
def search():
    """
    Gestisce le richieste di ricerca, coordina lo scraping dei vari siti
    e restituisce i risultati formattati.
    """
    try:
        print("\n=== NUOVA RICERCA ===")
        print(f"Metodo: {request.method}")
        
        # Estrai i parametri della richiesta
        if request.method == 'POST':
            print("Dati form:", request.form)
            search_query = request.form.get('prodotto', '').strip()
            siti_selezionati = request.form.getlist('siti')
        else:
            print("Dati query:", request.args)
            search_query = request.args.get('prodotto', '').strip()
            siti_selezionati = request.args.getlist('siti')

        print(f"Query di ricerca: '{search_query}'")
        print(f"Siti selezionati: {siti_selezionati}")

        # Se non c'è una query di ricerca, mostra risultati vuoti
        if not search_query:
            print("Nessuna query di ricerca specificata")
            return render_template('results.html', risultati=[], siti=[], prodotto='')

        # Salva il termine di ricerca originale per il template
        prodotto = search_query
        
        # Salva la ricerca nella cronologia se l'utente è loggato
        if current_user.is_authenticated and search_query:
            try:
                # Evita duplicati consecutivi
                last_search = SearchHistory.query.filter_by(user_id=current_user.id).order_by(SearchHistory.timestamp.desc()).first()
                if not last_search or last_search.search_term != search_query:
                    new_search = SearchHistory(user_id=current_user.id, search_term=search_query, filters=json.dumps(request.form if request.method == 'POST' else request.args))
                    db.session.add(new_search)
                    db.session.commit()
            except Exception as e:
                print(f"Errore salvataggio cronologia: {e}")
        
        # Inizializza le variabili per i risultati
        risultati = {}
        risultati_totali = []
        
        # Ottieni l'IP del client per la geolocalizzazione
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        # Se ci sono più IP (può succedere con proxy), prendi il primo
        if ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        # Usa il servizio ipapi.co per la geolocalizzazione
        paese = get_country_from_ip(client_ip)
        
        # Inizializza le statistiche
        stats = {
            'inizio_totale': time.time(),
            'siti': {}
        }
        
        # Esegui lo scraping dei vari siti
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {}
            
            # Avvia gli scraper in parallelo
            if sito_attivo(siti_selezionati, "thomann"):
                futures["thomann"] = executor.submit(run_scraper, "Thomann", cerca_thomann, prodotto)
                
            if sito_attivo(siti_selezionati, "musik_produktiv"):
                futures["musik_produktiv"] = executor.submit(run_scraper, "Musik Produktiv", cerca_musik_produktiv, prodotto, paese)
                
            if sito_attivo(siti_selezionati, "gear4music"):
                futures["gear4music"] = executor.submit(run_scraper, "Gear4music", cerca_gear4music, prodotto)
                
            if sito_attivo(siti_selezionati, "andertons"):
                futures["andertons"] = executor.submit(run_scraper, "Andertons", cerca_andertons, prodotto)
                
            # Gestisci lo scraper di Strumenti Musicali separatamente
            if sito_attivo(siti_selezionati, "strumentimusicali"):
                futures["strumentimusicali"] = executor.submit(run_scraper, "Strumenti Musicali", cerca_strumentimusicali, prodotto)
                
            # Gestisci gli altri scraper italiani in un unico worker
            if any(sito_attivo(siti_selezionati, s) for s in ["centrochitarre", "tomassone"]):
                futures["italia"] = executor.submit(scraping_italia, prodotto, siti_selezionati)
            
            # Raccogli i risultati
            risultati = {}
            for nome, future in futures.items():
                try:
                    if nome == "italia":
                        # Aggiorna i risultati con quelli degli scraper italiani
                        risultati_italia = future.result()
                        risultati.update(risultati_italia)
                    else:
                        risultati[nome] = future.result()
                        if isinstance(risultati[nome], list):
                            for r in risultati[nome]:
                                if isinstance(r, dict):
                                    r["sito"] = nome
                except Exception as e:
                    print(f"❌ Errore durante l'elaborazione dei risultati di {nome}: {str(e)[:200]}")
                    risultati[nome] = []

        # Prepara la lista dei risultati
        risultati_lista = []
        for sito, prodotti in risultati.items():
            if not isinstance(prodotti, list):
                print(f"⚠️ {sito}: risultati non validi (non è una lista)")
                continue
                
            print(f"📊 {sito}: {len(prodotti)} risultati")
            
            for p in prodotti:  # Cambiato 'prodotto' in 'p' per evitare conflitti
                if not isinstance(p, dict):
                    print(f"⚠️ {sito}: prodotto non valido (non è un dizionario)")
                    continue
                    
                # Aggiungi il sito al prodotto se non è già presente
                if 'sito' not in p:
                    p['sito'] = sito
                    
                risultati_lista.append(p)
        
        # --- LOGICA DI RICERCA IBRIDA ---
        
        # 1. Filtro Rigoroso (Strict)
        def filter_strict(items, query):
            if not query:
                return items
            tokens = query.lower().split()
            strict_items = []
            for item in items:
                nome = str(item.get('nome', '')).lower()
                if all(token in nome for token in tokens):
                    strict_items.append(item)
            return strict_items

        risultati_strict = filter_strict(risultati_lista, prodotto)

        # 2. Decisione: Strict o Fallback?
        search_mode = "strict"
        risultati_finali = []

        if len(risultati_strict) >= 5:
            # Se abbiamo abbastanza risultati precisi, usiamo quelli
            risultati_finali = risultati_strict
            search_mode = "strict"
        else:
            # Altrimenti, fallback alla ricerca più ampia
            risultati_finali = filtra_risultati(risultati_lista, prodotto)
            search_mode = "fuzzy"
            print(f"⚠️ Fallback a modalità FUZZY (trovati solo {len(risultati_strict)} strict)")
        
        print(f"🔍 Risultati finali ({search_mode}): {len(risultati_finali)}/{len(risultati_lista)}")
        
        # Ordina i risultati
        risultati_ordinati = sorted(
            risultati_finali,
            key=lambda x: (
                -x.get('punteggio_ricerca', 0),  # Ordina per punteggio decrescente
                float(x.get('prezzo', '999999').replace('.', '').replace(',', '.').replace('€', '').strip() or '999999')  # Poi per prezzo crescente
            )
        )
        
        # Raggruppa i risultati per sito
        risultati_per_sito = {}
        for r in risultati_ordinati:
            sito = r.get('sito', 'Altro')
            if sito not in risultati_per_sito:
                risultati_per_sito[sito] = []
            risultati_per_sito[sito].append(r)
        
        # Calcola il conteggio totale per sito
        conteggio_per_sito = {}
        for sito, risultati_sito in risultati_per_sito.items():
            conteggio_per_sito[sito] = len(risultati_sito)
        
        # Stampa il riepilogo
        print("\nRISULTATI PER SITO:")
        for sito, conteggio in conteggio_per_sito.items():
            print(f"- {sito}: {conteggio} risultati")

        filtro_sito = request.args.get("sito")
        if filtro_sito:
            risultati_ordinati = [r for r in risultati_ordinati if r.get('sito') == filtro_sito]
            print(f"\nFiltrato per sito: {filtro_sito} ({len(risultati_ordinati)} risultati)")
        
        # Applica i referral link ai risultati usando il database di referral
        for risultato in risultati_ordinati:
            if 'link' in risultato:
                # Cerca e applica il referral link dal database
                risultato['link'] = ReferralDBManager.get_referral_link(risultato['link'])
        
        # Prepara i dati per la paginazione
        pagina = request.args.get('pagina', 1, type=int)
        risultati_per_pagina = 100  # Aumentato da 20 a 100 risultati per pagina
        inizio = (pagina - 1) * risultati_per_pagina
        fine = inizio + risultati_per_pagina
        
        risultati_pagina = risultati_ordinati[inizio:fine]
        
        # Calcola il numero totale di pagine
        totale_pagine = (len(risultati_ordinati) + risultati_per_pagina - 1) // risultati_per_pagina
        
        # Calcola le statistiche finali
        stats['tempo_totale'] = round(time.time() - stats['inizio_totale'], 2)
        stats['totale_oggetti'] = len(risultati_ordinati)
        
        # Stampa il riepilogo
        print(f"\n{'='*50}")
        print("RIEPILOGO RICERCA")
        print(f"{'='*50}")
        
        for sito, dati in stats['siti'].items():
            if isinstance(dati, dict) and dati.get('stato') == 'errore':
                print(f"❌ {sito}: 0 risultati in {dati.get('tempo', 0):.2f}s - {dati.get('errore', 'Errore sconosciuto')}")
            elif isinstance(dati, dict):
                print(f"✅ {sito}: {dati.get('oggetti', 0)} risultati in {dati.get('tempo', 0):.2f}s")
        
        print(f"\nTOTALE: {stats['totale_oggetti']} risultati in {stats['tempo_totale']} secondi")
        print(f"{'='*50}\n")
        
        # Calcola la percentuale di sconto per ogni prodotto
        for r in risultati_ordinati:
            try:
                prezzo_attuale = float(r.get('prezzo_numerico', 0))
                prezzo_originale = float(r.get('prezzo_originale_numerico', 0))
                
                if prezzo_originale > prezzo_attuale and prezzo_originale > 0:
                    sconto = ((prezzo_originale - prezzo_attuale) / prezzo_originale) * 100
                    r['sconto_percentuale'] = round(sconto)
                else:
                    r['sconto_percentuale'] = 0
            except Exception:
                r['sconto_percentuale'] = 0

        # Identifica i Top 10 Sconti
        top_sconti = sorted(
            [r for r in risultati_ordinati if r.get('sconto_percentuale', 0) > 0],
            key=lambda x: x['sconto_percentuale'],
            reverse=True
        )[:10]

        # Prepara i dati per il template
        return render_template(
            'results.html',
            risultati=risultati_pagina,
            pagina=pagina,
            totale_pagine=totale_pagine,
            siti=conteggio_per_sito,
            prodotto=prodotto,
            filtro_sito=filtro_sito,
            current_lang=session.get('lang', 'en'),
            stats=stats,
            top_sconti=top_sconti,
            search_mode=search_mode
        )

    except Exception as e:
        print(f"❌ Errore durante la ricerca: {str(e)}")
        import traceback
        traceback.print_exc()
        return render_template(
            'error.html',
            error_message="Si è verificato un errore durante l'elaborazione della richiesta.",
            error_details=str(e)[:500],
            current_lang=session.get('lang', 'en')
        ), 500

@app.route('/contatti', methods=['GET', 'POST'])
def contatti():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        messaggio = request.form.get('messaggio')

        if not nome or not email or not messaggio:
            flash("Tutti i campi sono obbligatori.", "warning")
            return redirect('/contatti')

        try:
            msg = MIMEMultipart()
            msg['From'] = os.getenv('EMAIL_SENDER')
            msg['To'] = "antonio.web2music@gmail.com"
            msg['Subject'] = f'\U0001F4EC Nuovo messaggio da {nome}'

            body = f"Nome: {nome}\nEmail: {email}\nMessaggio:\n{messaggio}"
            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(os.getenv('EMAIL_SENDER'), os.getenv('EMAIL_PASSWORD'))
            server.sendmail(msg['From'], msg['To'], msg.as_string())
            server.quit()

            flash("Messaggio inviato con successo!", "success")
            return redirect('/contatti')

        except Exception as e:
            print(f"Errore invio email: {e}")
            flash("Errore durante l'invio del messaggio. Riprova più tardi.", "danger")
            return redirect('/contatti')

    return render_template('contatti.html', current_lang=session.get('lang', 'en'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        surname = request.form.get('surname')
        privacy_accepted = request.form.get('privacy_accepted') == 'on'
        newsletter_opt_in = request.form.get('newsletter_opt_in') == 'on'

        if not privacy_accepted:
            flash('Devi accettare la privacy policy per registrarti.', 'warning')
            return redirect(url_for('signup'))

        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email già registrata.', 'danger')
            return redirect(url_for('signup'))

        new_user = User(email=email, name=name, surname=surname, 
                        privacy_accepted=privacy_accepted, newsletter_opt_in=newsletter_opt_in)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        return redirect(url_for('index'))

    return render_template('signup.html', current_lang=session.get('lang', 'en'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Email o password non validi.', 'danger')

    return render_template('login.html', current_lang=session.get('lang', 'en'))

@app.route('/login/<provider>')
def login_oauth(provider):
    # Check if provider credentials are configured
    client_id = os.getenv(f'{provider.upper()}_CLIENT_ID')
    client_secret = os.getenv(f'{provider.upper()}_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        flash(f'Configurazione mancante per {provider}. Inserisci CLIENT_ID e CLIENT_SECRET nel file .env.', 'danger')
        return redirect(url_for('login'))

    client = oauth.create_client(provider)
    if not client:
        flash(f'Provider {provider} non supportato.', 'danger')
        return redirect(url_for('login'))
    
    redirect_uri = url_for('authorize_oauth', provider=provider, _external=True)
    return client.authorize_redirect(redirect_uri)

@app.route('/login/<provider>/callback')
def authorize_oauth(provider):
    client = oauth.create_client(provider)
    if not client:
        flash(f'Provider {provider} non supportato.', 'danger')
        return redirect(url_for('login'))
    
    try:
        token = client.authorize_access_token()
        
        user_info = None
        if provider == 'google':
            resp = client.get('userinfo')
            user_info = resp.json()
            email = user_info.get('email')
            name = user_info.get('given_name')
            surname = user_info.get('family_name')
            oauth_id = user_info.get('id')
            
        elif provider == 'facebook':
            resp = client.get('me?fields=id,name,email,first_name,last_name')
            user_info = resp.json()
            email = user_info.get('email')
            name = user_info.get('first_name')
            surname = user_info.get('last_name')
            oauth_id = user_info.get('id')
            
        elif provider == 'twitter':
            # Twitter API v2 logic might differ, using basic flow for now
            # Note: Twitter often requires elevated access for email
            resp = client.get('account/verify_credentials.json?include_email=true')
            user_info = resp.json()
            email = user_info.get('email')
            name = user_info.get('name').split(' ')[0] if user_info.get('name') else 'Twitter'
            surname = user_info.get('name').split(' ')[1] if user_info.get('name') and len(user_info.get('name').split(' ')) > 1 else 'User'
            oauth_id = str(user_info.get('id'))

        if not email:
            flash('Impossibile recuperare l\'email dal provider social.', 'danger')
            return redirect(url_for('login'))

        # Check if user exists
        user = User.query.filter_by(email=email).first()
        
        if not user:
            # Create new user
            user = User(
                email=email,
                name=name,
                surname=surname,
                oauth_provider=provider,
                oauth_id=oauth_id,
                privacy_accepted=True, # Implicit acceptance via social login
                newsletter_opt_in=False
            )
            db.session.add(user)
            db.session.commit()
        else:
            # Update existing user with oauth info if missing
            if not user.oauth_provider:
                user.oauth_provider = provider
                user.oauth_id = oauth_id
                db.session.commit()
        
        login_user(user)
        return redirect(url_for('index'))
        
    except Exception as e:
        print(f"OAuth Error: {e}")
        flash(f'Errore durante il login con {provider}: {str(e)}', 'danger')
        return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    history = SearchHistory.query.filter_by(user_id=current_user.id).order_by(SearchHistory.timestamp.desc()).limit(20).all()
    return render_template('profile.html', user=current_user, history=history, current_lang=session.get('lang', 'en'))

@app.cli.command("send-newsletter")
def send_newsletter_command():
    """Invia la newsletter settimanale."""
    from newsletter_manager import send_weekly_newsletter
    send_weekly_newsletter()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
