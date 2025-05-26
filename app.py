import warnings
# Disabilita tutti gli avvisi di urllib3
warnings.filterwarnings("ignore", category=DeprecationWarning, module='urllib3')

from flask import Flask, render_template, request, redirect, flash, session, url_for, g
import geocoder
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
        
        # Inizializza le variabili per i risultati
        risultati = {}
        risultati_totali = []
        
        # Ottieni l'IP del client per la geolocalizzazione
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        geo = geocoder.ip(client_ip)
        paese = geo.country if geo.ok and geo.country else "IT"
        
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
        
        # Applica il filtro di ricerca avanzato
        risultati_filtrati = filtra_risultati(risultati_lista, prodotto)
        print(f"🔍 Risultati dopo il filtro: {len(risultati_filtrati)}/{len(risultati_lista)}")
        
        # Ordina i risultati per punteggio di ricerca e prezzo
        risultati_ordinati = sorted(
            risultati_filtrati,
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
            stats=stats
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
