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

def _build_image_map(soup):
    """Estrae mappa product_id -> (image_url, slug_link) dalle card della pagina
    di ricerca. Evita una richiesta HTTP per prodotto (N+1) per og:image."""
    image_map = {}
    for a in soup.select('a[href*=".html"]'):
        img = a.find("img")
        if not img:
            continue
        href = a.get("href") or ""
        src = img.get("src") or img.get("data-src") or ""
        if not src:
            continue
        # Pattern URL immagine: pic-{id_padded}l/...
        m = re.search(r'/pic-0*(\d+)l/', src)
        if not m:
            continue
        pid = m.group(1)
        if pid not in image_map:
            full_link = href if href.startswith("http") else f"https://www.musik-produktiv.com{href}"
            image_map[pid] = (src, full_link)
    return image_map


def cerca_musik_produktiv(prodotto, paese="IT"):
    query = prodotto.replace(" ", "+")
    url = f"https://www.musik-produktiv.com/it/cerca.html?query={query}"
    print(f"\n🌐 Musik Produktiv: {url}")

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.text, "html.parser")

        script_tag = re.search(r'gtmDataLayer.push\((\{.*?"products":\s*\[.*?\])\}\);', str(soup), re.DOTALL)
        if not script_tag:
            print("❌ Nessun blocco prodotti trovato nel JS.")
            return []

        data_str = script_tag.group(1) + "}"
        data = json.loads(data_str)
        prodotti = data.get("products", [])
        image_map = _build_image_map(soup)

        print(f"✅ Trovati {len(prodotti)} prodotti su Musik Produktiv")

        iva_rate = IVA_PER_PAESI.get(paese.upper(), IVA_PER_PAESI["default"])

        risultati = []
        for item in prodotti:
            try:
                if not item or not isinstance(item, dict):
                    print("⚠ Dati prodotto non validi, salto")
                    continue
                    
                nome = item.get("name")
                if not nome:
                    print("⚠ Nome prodotto mancante, salto")
                    continue
                    
                try:
                    prezzo_str = str(item.get("price", "0")).replace(',', '.')
                    netto = float(prezzo_str) if prezzo_str.replace('.', '').isdigit() else 0
                except (ValueError, AttributeError):
                    netto = 0
                    
                if netto <= 0:
                    print(f"⚠ Prezzo non valido per {nome}, salto")
                    continue
                    
                ivato = round(netto * (1 + iva_rate), 2)
                
                try:
                    product_id = str(item.get('id', '')).strip()
                    if not product_id:
                        print(f"⚠ ID prodotto mancante per {nome}, salto")
                        continue
                        
                    img_entry = image_map.get(product_id)
                    if img_entry:
                        immagine, link = img_entry
                    else:
                        link = f"https://www.musik-produktiv.com/it/{product_id}.html"
                        immagine = "N/A"

                    # Estrazione prezzo originale (se presente nel JSON)
                    prezzo_originale = "N/A"
                    prezzo_originale_numerico = ivato # Default: nessun sconto

                    try:
                        # Cerca campi che potrebbero contenere il prezzo originale
                        # Nota: senza un dump JSON esatto, proviamo i nomi comuni
                        list_price_str = str(item.get("listPrice", item.get("oldPrice", item.get("rrp", "0")))).replace(',', '.')
                        list_price_netto = float(list_price_str) if list_price_str.replace('.', '').isdigit() else 0
                        
                        if list_price_netto > netto:
                            list_price_ivato = round(list_price_netto * (1 + iva_rate), 2)
                            prezzo_originale = f"€ {list_price_ivato:.2f}"
                            prezzo_originale_numerico = list_price_ivato
                    except Exception:
                        pass

                    risultati.append({
                        "nome": nome,
                        "prezzo": f"€ {ivato:.2f}",
                        "prezzo_numerico": ivato,
                        "prezzo_originale": prezzo_originale,
                        "prezzo_originale_numerico": prezzo_originale_numerico,
                        "link": link,
                        "immagine": immagine,
                        "sito": "Musik Produktiv"
                    })
                except Exception as e:
                    print(f"⚠ Errore nel processare il prodotto {nome}: {str(e)}")
                    
            except Exception as e:
                print(f"⚠ Errore imprevisto durante l'elaborazione di un prodotto: {str(e)}")
                continue

        return risultati

    except Exception as e:
        print(f"❌ Errore durante la richiesta o il parsing della pagina: {e}")
        return []

if __name__ == "__main__":
    prodotto = input("🔎 Prodotto da cercare su Musik Produktiv: ")
    risultati = cerca_musik_produktiv(prodotto)
    for r in risultati:
        print(f"[Musik Produktiv] {r['nome']} - {r['prezzo']} - {r['link']}")