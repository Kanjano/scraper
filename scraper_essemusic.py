from bs4 import BeautifulSoup
import time
from browser_manager import BrowserManager

def cerca_essemusic(prodotto):
    query = prodotto.replace(" ", "+")
    # URL aggiornato
    url = f"https://www.essemusic.it/shop?search={query}"
    print(f"🌐 Esse Music: {url}")

    driver = BrowserManager.create_driver()
    if not driver:
        return []

    risultati = []
    try:
        driver.get(url)
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Parsing dei risultati (Odoo structure)
        prodotti = soup.select(".oe_product")
        
        for p in prodotti:
            try:
                # Link e Immagine
                link_elem = p.select_one("a.oe_product_image_link")
                if not link_elem:
                    continue
                link = link_elem.get("href")
                if link and not link.startswith("http"):
                    link = "https://www.essemusic.it" + link
                
                img_elem = p.select_one("img")
                immagine = img_elem.get("src") if img_elem else "N/A"
                if immagine and not immagine.startswith("http"):
                    immagine = "https://www.essemusic.it" + immagine

                # Nome
                # Spesso è nell'alt dell'immagine o in un h6/div sotto
                if img_elem and img_elem.get("alt"):
                    nome = img_elem.get("alt")
                else:
                    nome = p.select_one("h6.o_wsale_products_item_title a").text.strip()

                # Prezzo
                # Cerchiamo .oe_currency_value o analizziamo onclick
                price_elem = p.select_one(".oe_currency_value")
                if price_elem:
                    prezzo = price_elem.text.strip()
                else:
                    # Fallback su onclick
                    import re
                    onclick = link_elem.get("onclick", "")
                    match = re.search(r"'price':\s*([\d\.]+)", onclick)
                    prezzo = match.group(1) if match else "Vedi sito"

                risultati.append({
                    "nome": nome,
                    "prezzo": prezzo,
                    "link": link,
                    "immagine": immagine,
                    "sito": "Esse Music"
                })
            except Exception as e:
                # print(f"Errore parsing prodotto: {e}")
                continue
    except Exception as e:
        print(f"⚠️ Errore Esse Music: {e}")
    finally:
        if not risultati and driver:
            print("⚠️ Nessun risultato trovato. Salvataggio HTML per debug...")
            try:
                with open("essemusic_dump.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
            except:
                pass
        BrowserManager.close_driver(driver)

    return risultati

def main():
    prodotto = input("🔎 Cosa vuoi cercare su Esse Music? ")
    risultati = cerca_essemusic(prodotto)
    for r in risultati:
        print(f"\n📦 {r['nome']}\n💶 {r['prezzo']}\n🔗 {r['link']}\n🖼️ {r['immagine']}")

if __name__ == "__main__":
    main()