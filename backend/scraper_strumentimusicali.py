"""
Scraper StrumentiMusicali.net via HTTP (requests + BeautifulSoup).
Sostituisce la vecchia implementazione Selenium per evitare contesa risorse
con gli altri scraper paralleli.
"""

import re
import logging
import requests
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36")

BASE = "https://www.strumentimusicali.net"


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


def search_strumentimusicali(prodotto, max_results=20):
    if not prodotto or not isinstance(prodotto, str):
        return []

    parole_chiave = [p.lower() for p in prodotto.split() if p.strip()]
    url = f"{BASE}/advanced_search_result.php?inc_subcat=1&keywords={quote_plus(prodotto)}"
    print(f"\n🌐 StrumentiMusicali.net: {url}")

    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": UA,
                "Accept-Language": "it-IT,it;q=0.9,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            timeout=20,
        )
        if resp.status_code != 200:
            logger.warning("StrumentiMusicali HTTP %s", resp.status_code)
            return []
        html = resp.text
    except Exception as e:
        logger.warning("StrumentiMusicali errore richiesta: %s", e)
        return []

    soup = BeautifulSoup(html, "html.parser")

    # Layout a tabella: ogni prodotto è in più td.productListing-data.
    # Aggreghiamo per link prodotto univoco.
    prodotti = {}
    for row in soup.select("tr"):
        name_el = row.select_one(".listing_prod_name")
        if not name_el:
            continue
        a = row.select_one("a.pdlist[href*=product_info]") or row.select_one("a[href*=product_info]")
        if not a:
            continue
        link = a.get("href", "").strip()
        if not link:
            continue

        nome = name_el.get_text(" ", strip=True)
        nome_lower = nome.lower()
        if not all(k in nome_lower for k in parole_chiave):
            continue

        price_el = row.select_one(".productSpecialPrice") or row.select_one(".productPrice")
        prezzo_num = _parse_price(price_el.get_text(strip=True)) if price_el else 0.0

        old_el = row.select_one(".productPriceOld, .productPrice s, s .productPrice, del")
        prezzo_originale_numerico = prezzo_num
        prezzo_originale = "N/A"
        if old_el:
            old_v = _parse_price(old_el.get_text(strip=True))
            if old_v > prezzo_num > 0:
                prezzo_originale_numerico = old_v
                prezzo_originale = f"€ {old_v:.2f}"

        img_el = row.select_one("img.unveil") or row.select_one("img")
        immagine = "N/A"
        if img_el:
            immagine = img_el.get("data-src") or img_el.get("src") or "N/A"
            if immagine and immagine.startswith("data:"):
                immagine = img_el.get("data-src") or "N/A"

        existing = prodotti.get(link)
        if existing:
            # Aggiorna campi mancanti
            if existing["prezzo_numerico"] <= 0 and prezzo_num > 0:
                existing["prezzo_numerico"] = prezzo_num
                existing["prezzo"] = f"€ {prezzo_num:.2f}"
            if existing["immagine"] in (None, "N/A") and immagine != "N/A":
                existing["immagine"] = immagine
            continue

        prodotti[link] = {
            "nome": nome,
            "prezzo": f"€ {prezzo_num:.2f}" if prezzo_num > 0 else "N/A",
            "prezzo_numerico": prezzo_num,
            "prezzo_originale": prezzo_originale,
            "prezzo_originale_numerico": prezzo_originale_numerico,
            "link": link,
            "immagine": immagine,
            "sito": "StrumentiMusicali.net",
        }

    risultati = [p for p in prodotti.values() if p["prezzo_numerico"] > 0][:max_results]
    print(f"📦 StrumentiMusicali.net totale: {len(risultati)}")
    return risultati


# Compatibility aliases
def cerca_strumentimusicali(prodotto, max_results=20):
    return search_strumentimusicali(prodotto, max_results=max_results)


if __name__ == "__main__":
    prodotto = input("🔎 Prodotto da cercare su StrumentiMusicali.net: ")
    for r in search_strumentimusicali(prodotto):
        print(f"[StrumentiMusicali] {r['nome']} - {r['prezzo']} - {r['link']}")
