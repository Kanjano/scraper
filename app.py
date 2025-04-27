from flask import Flask, render_template, request, redirect, flash
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

from scraper_thomann import cerca_thomann
from scraper_musik_produktiv import cerca_musik_produktiv
from scraper_gear4music import cerca_gear4music
from scraper_andertons import cerca_andertons
from scraper_italia import cerca_centrochitarre, cerca_tomassone

load_dotenv()

app = Flask(__name__)
app.secret_key = 'supersegreto'

# -- Utility fuzzy match per il filtro titolo --
def parole_rilevanti(testo):
    stopwords = {"il", "lo", "la", "i", "gli", "le", "di", "a", "da", "in", "su", "con", "per", "tra", "fra", "e"}
    parole = re.findall(r'\b\w+\b', testo.lower())
    return [p for p in parole if p not in stopwords]

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
    return render_template('index.html')

@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        prodotto = request.form.get('prodotto')
        siti_selezionati = request.form.getlist('siti')
    else:
        prodotto = request.args.get('prodotto')
        siti_selezionati = request.args.getlist('siti')

    if not prodotto:
        return render_template('results.html', risultati=[], siti=[])

    def sito_attivo(nome):
        return not siti_selezionati or nome in siti_selezionati

    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    geo = geocoder.ip(client_ip)
    paese = geo.country if geo.ok and geo.country else "IT"
    print(f"\U0001F30D IP: {client_ip}, Paese rilevato: {paese if geo.ok else 'N/D'}")

    def timed_scraper(func, *args):
        start = time.time()
        result = func(*args)
        elapsed = time.time() - start
        print(f"⏱ Tempo per {func.__name__}: {elapsed:.2f} secondi | Prodotti estratti: {len(result)}")
        return result

    risultati = {}

    def scraping_italia():
        italia_scrapers = {
            "Centro Chitarre": cerca_centrochitarre,
            "Tomassone": cerca_tomassone,
        }

        local_risultati = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            future_to_site = {
                pool.submit(timed_scraper, scraper, prodotto): sito
                for sito, scraper in italia_scrapers.items() if sito_attivo(sito)
            }
            for future in as_completed(future_to_site):
                sito = future_to_site[future]
                try:
                    local_risultati[sito] = future.result()
                    for r in local_risultati[sito]:
                        r["sito"] = sito
                except Exception as e:
                    print(f"❌ Errore scraping {sito}: {e}")
                    local_risultati[sito] = []
        return local_risultati

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        if sito_attivo("Thomann"):
            futures["Thomann"] = executor.submit(timed_scraper, cerca_thomann, prodotto)
        if sito_attivo("Musik Produktiv"):
            futures["Musik Produktiv"] = executor.submit(timed_scraper, cerca_musik_produktiv, prodotto, paese)
        if sito_attivo("Gear4music"):
            futures["Gear4music"] = executor.submit(timed_scraper, cerca_gear4music, prodotto)
        if sito_attivo("Andertons"):
            futures["Andertons"] = executor.submit(timed_scraper, cerca_andertons, prodotto)
        if any(sito_attivo(s) for s in ["Centro Chitarre", "Tomassone"]):
            futures["Italia"] = executor.submit(scraping_italia)

        for sito, future in futures.items():
            try:
                if sito == "Italia":
                    risultati.update(future.result())
                else:
                    risultati[sito] = future.result()
                    for r in risultati[sito]:
                        r["sito"] = sito
            except Exception as e:
                print(f"❌ Errore scraping {sito}: {e}")
                risultati[sito] = []

    risultati_totali = sum(risultati.values(), [])

    # --- FILTRO FUZZY SU RISULTATI TOTALI ---
    parole_chiave = parole_rilevanti(prodotto)
    risultati_totali = [r for r in risultati_totali if match_fuzzy(r["nome"], parole_chiave)]

    filtro_sito = request.args.get("sito")
    if filtro_sito:
        risultati_totali = [r for r in risultati_totali if r["sito"] == filtro_sito]

    sort = request.args.get("sort", "prezzo_desc")
    sort_options = {
        "prezzo_asc": lambda x: x["prezzo_numerico"] if x["prezzo_numerico"] is not None else float('inf'),
        "prezzo_desc": lambda x: -(x["prezzo_numerico"] if x["prezzo_numerico"] is not None else 0),
        "sito": lambda x: x["sito"]
    }
    key_func = sort_options.get(sort, lambda x: -(x["prezzo_numerico"] if x["prezzo_numerico"] is not None else 0))
    risultati_totali.sort(key=key_func)

    return render_template(
        'results.html',
        risultati=risultati_totali,
        siti=list(risultati.keys()),
        prodotto=prodotto
    )

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

    return render_template('contatti.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
