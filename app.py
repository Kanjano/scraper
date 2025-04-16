from flask import Flask, render_template, request
import geocoder

from scraper_thomann import cerca_thomann
from scraper_musik_produktiv import cerca_musik_produktiv
from scraper_gear4music import cerca_gear4music
from scraper_andertons import cerca_andertons  # ✅ nuovo import

app = Flask(__name__)

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

    # 🌍 Ottieni paese da IP del client
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    geo = geocoder.ip(client_ip)
    paese = geo.country if geo.ok and geo.country else "IT"
    print(f"🌍 IP: {client_ip}, Paese rilevato: {paese}")

    # Cerca prodotti
    risultati_thomann = cerca_thomann(prodotto)
    risultati_musik = cerca_musik_produktiv(prodotto, paese=paese)
    risultati_gear4music = cerca_gear4music(prodotto)
    risultati_andertons = cerca_andertons(prodotto)  # ✅ nuova riga

    # Etichetta i risultati
    for r in risultati_thomann:
        r["sito"] = "Thomann"
    for r in risultati_musik:
        r["sito"] = "Musik Produktiv"
    for r in risultati_gear4music:
        r["sito"] = "Gear4music"
    for r in risultati_andertons:
        r["sito"] = "Andertons"  # ✅ nuova etichetta

    # Unisci tutti
    risultati_totali = (
        risultati_thomann +
        risultati_musik +
        risultati_gear4music +
        risultati_andertons  # ✅ aggiunto Andertons
    )

    # Filtra per sito (se richiesto)
    filtro_sito = request.args.get("sito")
    if filtro_sito:
        risultati_totali = [r for r in risultati_totali if r["sito"] == filtro_sito]

    # Ordina
    sort = request.args.get("sort", "prezzo_desc")
    if sort == "prezzo_asc":
        risultati_totali.sort(key=lambda x: x["prezzo_numerico"])
    elif sort == "sito":
        risultati_totali.sort(key=lambda x: x["sito"])
    else:
        risultati_totali.sort(key=lambda x: x["prezzo_numerico"], reverse=True)

    return render_template(
        'results.html',
        risultati=risultati_totali,
        siti=["Thomann", "Musik Produktiv", "Gear4music", "Andertons"],  # ✅ aggiornato
        prodotto=prodotto
    )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')