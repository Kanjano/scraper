import re
import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36")


def _parse_price(raw: str) -> float:
    try:
        clean = re.sub(r"[^\d,\.]", "", raw)
        if '.' in clean and ',' in clean:
            clean = clean.replace('.', '').replace(',', '.')
        elif ',' in clean:
            clean = clean.replace(',', '.')
        return round(float(clean), 2) if clean else 0.0
    except Exception:
        return 0.0


def cerca_centrochitarre(prodotto):
    query = prodotto.replace(" ", "+")
    parole_chiave = [p.lower() for p in prodotto.split() if p.strip()]
    url = f"https://www.centrochitarre.com/catalogsearch/result/?q={query}"
    print(f"\n🌐 Centro Chitarre: {url}")

    try:
        resp = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9"},
                            timeout=20)
        if resp.status_code != 200:
            print(f"⚠️ Centro Chitarre HTTP {resp.status_code}")
            return []
        html = resp.text
    except Exception as e:
        print(f"⚠️ Errore richiesta Centro Chitarre: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    risultati = []
    seen = set()

    for card in soup.select("li.product-item, .product-item"):
        try:
            a = card.select_one("a.product-item-link") or card.find("a", href=True)
            if not a:
                continue
            nome = a.get_text(strip=True)
            link = a.get("href", "").strip()
            if not nome or not link or link in seen:
                continue

            nome_lower = nome.lower()
            if not all(k in nome_lower for k in parole_chiave):
                continue

            prezzo_eur = 0.0
            price_data = card.select_one("[data-price-amount]")
            if price_data and price_data.get("data-price-amount"):
                try:
                    prezzo_eur = float(price_data["data-price-amount"])
                except Exception:
                    pass
            if prezzo_eur <= 0:
                price_el = card.select_one(".price-wrapper .price, span.price")
                if price_el:
                    prezzo_eur = _parse_price(price_el.get_text(strip=True))
            if prezzo_eur <= 0:
                continue

            immagine = "N/A"
            img = card.select_one("img.product-image-photo, img")
            if img:
                immagine = img.get("src") or img.get("data-src") or "N/A"

            prezzo_originale = "N/A"
            prezzo_originale_numerico = prezzo_eur
            old = card.select_one(".old-price [data-price-amount], .old-price .price")
            if old:
                if old.get("data-price-amount"):
                    try:
                        old_v = float(old["data-price-amount"])
                    except Exception:
                        old_v = _parse_price(old.get_text(strip=True))
                else:
                    old_v = _parse_price(old.get_text(strip=True))
                if old_v > prezzo_eur:
                    prezzo_originale = f"€ {old_v:.2f}"
                    prezzo_originale_numerico = old_v

            seen.add(link)
            risultati.append({
                "nome": nome,
                "prezzo": f"€ {prezzo_eur:.2f}",
                "prezzo_numerico": prezzo_eur,
                "prezzo_originale": prezzo_originale,
                "prezzo_originale_numerico": prezzo_originale_numerico,
                "immagine": immagine,
                "link": link,
                "sito": "Centro Chitarre",
            })

        except Exception:
            continue

    print(f"📦 Centro Chitarre totale: {len(risultati)}")
    return risultati


if __name__ == "__main__":
    prodotto = input("🔎 Prodotto da cercare su Centro Chitarre: ")
    risultati = cerca_centrochitarre(prodotto)
    for r in risultati:
        print(f"[Centro Chitarre] {r['nome']} - {r['prezzo']} - {r['link']}")
