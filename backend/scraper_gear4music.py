import re
import json
import time
from bs4 import BeautifulSoup
from multiprocessing import Pool
from browser_manager import BrowserManager

def estrai_immagine_prodotto(driver, link_prodotto):
    try:
        driver.get(link_prodotto)
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        img_tag = soup.select_one("img.main-image[data-src]")
        if img_tag:
            return img_tag["data-src"]
    except Exception as e:
        print(f"❌ Errore immagine {link_prodotto}: {e}")
    return "N/A"

def cerca_gear4music(prodotto):
    query = prodotto.replace(" ", "+")
    parole_chiave = [p.lower() for p in prodotto.split()]
    url = f"https://www.gear4music.it/it/search/?str_search_phrase={query}"
    print(f"\n🌐 Gear4Music: {url}")

    import os
    # Default a True (headless) per produzione, ma sovrascrivibile via env
    use_headless = os.environ.get('HEADLESS', 'true').lower() == 'true'
    driver = BrowserManager.create_driver(headless=use_headless)
    if not driver:
        return []

    risultati = []
    try:
        driver.get(url)

        for i in range(5):
            driver.execute_script("window.scrollBy(0, document.body.scrollHeight / 5);")
            time.sleep(1.5)

        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        
        # Cerca i prodotti nel DOM (selettori identificati via browser inspector)
        product_cards = soup.select("li.g4m-list-product")
        if not product_cards:
            # Fallback per altri layout possibili
            product_cards = soup.select(".product-result, .result-item, .product-card")
            
        print(f"✅ Trovati {len(product_cards)} card prodotto nel DOM")

        for card in product_cards:
            try:
                # Titolo
                title_elem = card.select_one("h3.title, .product-title, .name")
                if not title_elem:
                    continue
                nome = title_elem.get_text(strip=True)
                
                # Filtro parole chiave
                nome_lower = nome.lower()
                if not all(k in nome_lower for k in parole_chiave):
                    continue

                # Link
                link_elem = card.find("a", href=True)
                link = "N/A"
                if link_elem:
                    href = link_elem["href"]
                    if href.startswith("/"):
                         link = "https://www.gear4music.it" + href
                    else:
                         link = href
                    # Immagine
                    img_elem = card.select_one("img")
                    immagine = "N/A"
                    if img_elem:
                        immagine = img_elem.get("data-src") or img_elem.get("src") or "N/A"
                
                # Prezzo
                price_elem = card.select_one("span.c-val, .price, .product-price")
                price_eur = 0.0
                prezzo_str = "N/A"
                
                if price_elem:
                    prezzo_str_raw = price_elem.get_text(strip=True)
                    # Gestione formato "2.113,00" -> 2113.00
                    try:
                        # Rimuovi currency e spazi
                        p_clean = re.sub(r'[^\d,\.]', '', prezzo_str_raw)
                        if ',' in p_clean and '.' in p_clean:
                             if p_clean.rfind(',') > p_clean.rfind('.'): # 2.113,00
                                 p_clean = p_clean.replace('.', '').replace(',', '.')
                             else: # 1,234.56
                                 p_clean = p_clean.replace(',', '')
                        elif ',' in p_clean:
                                 p_clean = p_clean.replace(',', '.')
                        # Se solo punti, assume siano migliaia se >2 cifre dopo
                        
                        price_eur = float(p_clean)
                        prezzo_str = f"€ {price_eur:.2f}"
                    except:
                        pass

                # Prezzo Originale (RRP)
                # Gear4music spesso mostra 'Prezzo consigliato: € ...' o simile
                rrp_elem = card.select_one(".rrp, .old-price, span.crossed")
                prezzo_originale = "N/A"
                prezzo_originale_numerico = 0.0
                
                if rrp_elem:
                    try:
                        rrp_raw = rrp_elem.get_text(strip=True)
                        rrp_clean = re.sub(r'[^\d,\.]', '', rrp_raw)
                        rrp_clean = rrp_clean.replace('.', '').replace(',', '.')
                        prezzo_originale_numerico = float(rrp_clean)
                        prezzo_originale = f"€ {prezzo_originale_numerico:.2f}"
                    except:
                        pass
                else:
                    prezzo_originale_numerico = price_eur # Se non c'è sconto

                risultati.append({
                    "nome": nome,
                    "prezzo": prezzo_str,
                    "prezzo_numerico": price_eur,
                    "prezzo_originale": prezzo_originale,
                    "prezzo_originale_numerico": prezzo_originale_numerico,
                    "link": link,
                    "immagine": immagine,
                    "sito": "Gear4music"
                })

            except Exception as e:
                 print(f"⚠️ Errore estrazione card: {e}")
                 continue

    except Exception as e:
        print(f"❌ Errore generale Gear4music: {e}")
    finally:
        BrowserManager.close_driver(driver)
        
    return risultati

def cerca_multiprodotti(lista_prodotti, num_processi=4):
    with Pool(processes=num_processi) as pool:
        risultati_totali = pool.map(cerca_gear4music, lista_prodotti)

    # Flatten dei risultati (ogni item è una lista)
    flat = [item for sublist in risultati_totali for item in sublist]
    print(f"\n✅ Totale prodotti trovati: {len(flat)}")
    return flat

if __name__ == "__main__":
    prodotto = input("🔎 Prodotto da cercare su Gear4music: ")
    risultati = cerca_gear4music(prodotto)
    for r in risultati:
        print(f"[Gear4music] {r['nome']} - {r['prezzo']} - {r['link']}")