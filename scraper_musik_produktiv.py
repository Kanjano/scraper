import requests
import re
import json
from bs4 import BeautifulSoup

IVA_PER_PAESI = {
    "DE": 0.19,
    "IT": 0.22,
    "FR": 0.20,
    "ES": 0.21,
    "NL": 0.21,
    "default": 0.22
}

def get_musikprodukt_image(link):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(link, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        og_image = soup.find("meta", property="og:image")
        return og_image["content"] if og_image else "N/A"
    except Exception as e:
        print(f"⚠ Immagine non trovata per {link}: {e}")
        return "N/A"

def cerca_musik_produktiv(prodotto, paese="IT"):
    query = prodotto.replace(" ", "+")
    url = f"https://www.musik-produktiv.com/it/cerca.html?query={query}"
    print(f"\n🌐 Musik Produktiv: {url}")

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        script_tag = re.search(r'gtmDataLayer.push\((\{.*?"products":\s*\[.*?\])\}\);', str(soup), re.DOTALL)
        if not script_tag:
            print("❌ Nessun blocco prodotti trovato nel JS.")
            return []

        data_str = script_tag.group(1) + "}"
        data = json.loads(data_str)
        prodotti = data.get("products", [])

        print(f"✅ Trovati {len(prodotti)} prodotti su Musik Produktiv")

        iva_rate = IVA_PER_PAESI.get(paese.upper(), IVA_PER_PAESI["default"])

        risultati = []
        for item in prodotti:
            try:
                nome = item.get("name", "N/A")
                netto = float(item.get("price", 0))
                ivato = round(netto * (1 + iva_rate), 2)

                link = f"https://www.musik-produktiv.com/it/{item['id']}.html"
                immagine = get_musikprodukt_image(link)

                risultati.append({
                    "nome": nome,
                    "prezzo": f"€ {ivato:.2f}",
                    "prezzo_numerico": ivato,
                    "link": link,
                    "immagine": immagine,
                    "sito": "Musik Produktiv"
                })
            except Exception as e:
                print(f"⚠ Errore nel parsing di un prodotto: {e}")
                continue

        return risultati

    except Exception as e:
        print(f"❌ Errore durante la richiesta o il parsing della pagina: {e}")
        return []