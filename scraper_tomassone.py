import time
import re
from bs4 import BeautifulSoup
from browser_manager import BrowserManager

def cerca_tomassone(prodotto):
    query = prodotto.replace(" ", "+")
    url = f"https://www.tomassone.it/ita/catalogsearch/result/?q={query}"
    print(f"\n🌐 Tomassone: {url}")

    driver = BrowserManager.create_driver()
    if not driver:
        return []

    try:
        driver.get(url)
        time.sleep(3)
        html = driver.page_source
    except Exception as e:
        print(f"⚠️ Errore durante il caricamento della pagina: {e}")
        BrowserManager.close_driver(driver)
        return []

    soup = BeautifulSoup(html, "html.parser")
    risultati = []

    try:
        for card in soup.select(".product-item-info"):
            try:
                # Estrai il nome
                nome_elem = card.select_one(".product-item-link")
                if not nome_elem:
                    continue
                    
                nome = nome_elem.get_text(strip=True)
                if not nome:
                    continue
                    
                # Estrai il link
                link = nome_elem.get("href", "").strip()
                if not link:
                    continue
                    
                # Estrai il prezzo
                prezzo_elem = card.select_one(".price")
                if not prezzo_elem:
                    continue
                    
                prezzo_raw = prezzo_elem.get_text(strip=True)
                try:
                    prezzo_num = float(re.sub(r"[^\d,]", "", prezzo_raw).replace(",", "."))
                except (ValueError, AttributeError):
                    continue

                # Estrai l'immagine
                img_tag = card.select_one("img")
                immagine = "N/A"
                if img_tag:
                    immagine = img_tag.get("src") or img_tag.get("data-src") or "N/A"
                    if immagine and not immagine.startswith("http") and not immagine.startswith("data:"):
                        immagine = "https://www.tomassone.it" + ("" if immagine.startswith("/") else "/") + immagine

                risultati.append({
                    "nome": nome,
                    "prezzo": f"€{prezzo_num:.2f}".replace(".", ","),
                    "prezzo_numerico": prezzo_num,
                    "link": link,
                    "immagine": immagine,
                    "sito": "Tomassone"
                })
                
            except Exception as e:
                print(f"⚠️ Errore parsing prodotto: {e}")
                continue
    except Exception as e:
        print(f"⚠️ Errore generale durante il parsing: {e}")
    finally:
        BrowserManager.close_driver(driver)

    print(f"\n📦 Totale prodotti trovati su Tomassone: {len(risultati)}")
    return risultati

if __name__ == "__main__":
    prodotto = input("🔎 Prodotto da cercare su Tomassone: ")
    risultati = cerca_tomassone(prodotto)
    for r in risultati:
        print(f"[Tomassone] {r['nome']} - {r['prezzo']} - {r['link']}")
