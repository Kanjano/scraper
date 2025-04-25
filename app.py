from flask import Flask, render_template, request, redirect, flash
import geocoder
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import os
from dotenv import load_dotenv

# Import scraper
from scraper_thomann import cerca_thomann
from scraper_musik_produktiv import cerca_musik_produktiv
from scraper_gear4music import cerca_gear4music
from scraper_andertons import cerca_andertons
from scraper_italia import cerca_tomassone, cerca_centrochitarre

load_dotenv()

app = Flask(__name__)
app.secret_key = 'supersegreto'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        prodotto = request.form.get('prodotto')
    else:
        prodotto = request.args.get('prodotto')

    if not prodotto:
        return render_template('results.html', risultati=[], siti=[])

    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    geo = geocoder.ip(client_ip)
    paese = geo.country if geo.ok and geo.country else "IT"
    print(f"\U0001F30D IP: {client_ip}, Paese rilevato: {paese if geo.ok else 'N/D'}")

    def timed_scraper(nome, func, *args):
        try:
            start = time.time()
            result = func(*args)
            elapsed = time.time() - start
            print(f"⏱ Tempo per {nome}: {elapsed:.2f} secondi | Prodotti estratti: {len(result)}")
            for r in result:
                r["sito"] = nome
            return result
        except Exception as e:
            print(f"❌ Errore scraping {nome}: {e}")
            return []

    # Eseguiamo uno alla volta
    risultati = []
    risultati += timed_scraper("Thomann", cerca_thomann, prodotto)
    risultati += timed_scraper("Musik Produktiv", cerca_musik_produktiv, prodotto, paese)
    risultati += timed_scraper("Centro Chitarre", cerca_centrochitarre, prodotto)
    risultati += timed_scraper("Tomassone", cerca_tomassone, prodotto)
    risultati += timed_scraper("Gear4music", cerca_gear4music, prodotto)
    risultati += timed_scraper("Andertons", cerca_andertons, prodotto)

    # Filtro
    filtro_sito = request.args.get("sito")
    if filtro_sito:
        risultati = [r for r in risultati if r["sito"] == filtro_sito]

    sort = request.args.get("sort", "prezzo_desc")
    sort_options = {
        "prezzo_asc": lambda x: x["prezzo_numerico"],
        "prezzo_desc": lambda x: -x["prezzo_numerico"],
        "sito": lambda x: x["sito"]
    }
    key_func = sort_options.get(sort, lambda x: -x["prezzo_numerico"])
    risultati.sort(key=key_func)

    return render_template('results.html', risultati=risultati, siti=list(set(r["sito"] for r in risultati)), prodotto=prodotto)

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