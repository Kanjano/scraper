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


def cerca_tomassone(prodotto):
    query = prodotto.replace(" ", "+")
    parole_chiave = [p.lower() for p in prodotto.split() if p.strip()]
    url = f"https://www.tomassone.it/ita/catalogsearch/result/?q={query}"
    print(f"\n🌐 Tomassone: {url}")

    try:
        resp = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9"},
                            timeout=20)
        if resp.status_code != 200:
            print(f"⚠️ Tomassone HTTP {resp.status_code}")
            return []
        html = resp.text
    except Exception as e:
        print(f"⚠️ Errore richiesta Tomassone: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    risultati = []
    seen = set()

    for card in soup.select(".product-item-info, li.product-item"):
        try:
            a = card.select_one(".product-item-link") or card.find("a", href=True)
            if not a:
                continue
            nome = a.get_text(strip=True)
            link = a.get("href", "").strip()
            if not nome or not link or link in seen:
                continue

            nome_lower = nome.lower()
            if not all(k in nome_lower for k in parole_chiave):
                continue

            # Prezzo: privilegia data-price-amount
            prezzo_num = 0.0
            price_el = card.select_one("[data-price-amount]")
            if price_el and price_el.get("data-price-amount"):
                try:
                    prezzo_num = float(price_el["data-price-amount"])
                except Exception:
                    pass
            if prezzo_num <= 0:
                price_text_el = card.select_one(".price-wrapper .price, span.price")
                if price_text_el:
                    prezzo_num = _parse_price(price_text_el.get_text(strip=True))
            if prezzo_num <= 0:
                continue

            # Immagine
            img_tag = card.select_one("img.product-image-photo, img")
            immagine = "N/A"
            if img_tag:
                immagine = img_tag.get("src") or img_tag.get("data-src") or "N/A"
                if immagine and not immagine.startswith(("http", "data:")):
                    immagine = "https://www.tomassone.it" + ("" if immagine.startswith("/") else "/") + immagine

            # Prezzo originale
            prezzo_originale = "N/A"
            prezzo_originale_numerico = prezzo_num
            old_el = card.select_one(".old-price [data-price-amount], .old-price .price")
            if old_el:
                if old_el.get("data-price-amount"):
                    try:
                        old_v = float(old_el["data-price-amount"])
                    except Exception:
                        old_v = _parse_price(old_el.get_text(strip=True))
                else:
                    old_v = _parse_price(old_el.get_text(strip=True))
                if old_v > prezzo_num:
                    prezzo_originale = f"€{old_v:.2f}".replace(".", ",")
                    prezzo_originale_numerico = old_v

            seen.add(link)
            risultati.append({
                "nome": nome,
                "prezzo": f"€{prezzo_num:.2f}".replace(".", ","),
                "prezzo_numerico": prezzo_num,
                "prezzo_originale": prezzo_originale,
                "prezzo_originale_numerico": prezzo_originale_numerico,
                "link": link,
                "immagine": immagine,
                "sito": "Tomassone",
            })

        except Exception as e:
            print(f"⚠️ Errore parsing Tomassone: {e}")
            continue

    print(f"📦 Tomassone totale: {len(risultati)}")
    return risultati


if __name__ == "__main__":
    prodotto = input("🔎 Prodotto da cercare su Tomassone: ")
    risultati = cerca_tomassone(prodotto)
    for r in risultati:
        print(f"[Tomassone] {r['nome']} - {r['prezzo']} - {r['link']}")
