import re
import time
from bs4 import BeautifulSoup
from browser_manager import BrowserManager


def _parse_price(raw: str) -> float:
    try:
        clean = re.sub(r'[^\d,\.]', '', raw)
        if ',' in clean and '.' in clean:
            if clean.rfind(',') > clean.rfind('.'):
                clean = clean.replace('.', '').replace(',', '.')
            else:
                clean = clean.replace(',', '')
        elif ',' in clean:
            clean = clean.replace(',', '.')
        return float(clean) if clean else 0.0
    except Exception:
        return 0.0


def cerca_gear4music(prodotto):
    query = prodotto.replace(" ", "+")
    parole_chiave = [p.lower() for p in prodotto.split() if p.strip()]
    url = f"https://www.gear4music.it/it/search/?str_search_phrase={query}"
    print(f"\n🌐 Gear4Music: {url}")

    driver = BrowserManager.create_driver()
    if not driver:
        return []

    risultati = []
    try:
        driver.get(url)
        time.sleep(3)
        for _ in range(4):
            driver.execute_script("window.scrollBy(0, document.body.scrollHeight / 4);")
            time.sleep(1.0)

        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        # Selector reale del listing principale Gear4Music
        cards = soup.select('li.restricted-inv-notice-row, li[data-g4m-inv]')
        print(f"✅ Trovate {len(cards)} card prodotto")

        seen_ids = set()
        for card in cards:
            try:
                inv_id = card.get('data-g4m-inv')
                if not inv_id or inv_id in seen_ids:
                    continue

                a = card.select_one('a.list-row-container[href]') or card.find('a', href=True)
                if not a:
                    continue

                href = a.get('href', '')
                if href.startswith('/'):
                    link = "https://www.gear4music.it" + href
                else:
                    link = href

                title_el = card.select_one('h3') or a
                nome = (title_el.get_text(strip=True) if title_el else a.get('title', '')).strip()
                if not nome:
                    nome = a.get('title', '')
                if not nome:
                    continue

                # Filtra per parole chiave (tutte presenti nel nome)
                nome_lower = nome.lower()
                if not all(k in nome_lower for k in parole_chiave):
                    continue

                # Immagine
                img = card.select_one('img[data-src], img[src]')
                immagine = "N/A"
                if img:
                    src = img.get('data-src') or img.get('src')
                    if src and 'sashleft' not in src and 'invsash' not in src:
                        immagine = src

                # Prezzo: span.c-val ha attributo content="1399.00"
                price_eur = 0.0
                prezzo_str = "N/A"
                cval = card.select_one('span.c-val[content]')
                if cval and cval.get('content'):
                    try:
                        price_eur = float(cval['content'])
                    except Exception:
                        price_eur = _parse_price(cval.get_text(strip=True))
                else:
                    price_el = card.select_one('span.price, .c-val')
                    if price_el:
                        price_eur = _parse_price(price_el.get_text(strip=True))

                if price_eur > 0:
                    prezzo_str = f"€ {price_eur:.2f}"

                # Prezzo originale (RRP / barrato)
                prezzo_originale_numerico = price_eur
                prezzo_originale = "N/A"
                rrp = card.select_one('.rrp .c-val[content], .was-price .c-val[content], del .c-val[content]')
                if rrp and rrp.get('content'):
                    try:
                        rrp_val = float(rrp['content'])
                        if rrp_val > price_eur > 0:
                            prezzo_originale_numerico = rrp_val
                            prezzo_originale = f"€ {rrp_val:.2f}"
                    except Exception:
                        pass

                if price_eur <= 0:
                    continue

                seen_ids.add(inv_id)
                risultati.append({
                    "nome": nome,
                    "prezzo": prezzo_str,
                    "prezzo_numerico": price_eur,
                    "prezzo_originale": prezzo_originale,
                    "prezzo_originale_numerico": prezzo_originale_numerico,
                    "link": link,
                    "immagine": immagine,
                    "sito": "Gear4music",
                })

            except Exception as e:
                print(f"⚠️ Errore card Gear4music: {e}")
                continue

    except Exception as e:
        print(f"❌ Errore generale Gear4music: {e}")
        raise
    finally:
        BrowserManager.close_driver(driver)

    print(f"📦 Gear4music totale: {len(risultati)}")
    return risultati


if __name__ == "__main__":
    prodotto = input("🔎 Prodotto da cercare su Gear4music: ")
    risultati = cerca_gear4music(prodotto)
    for r in risultati:
        print(f"[Gear4music] {r['nome']} - {r['prezzo']} - {r['link']}")
