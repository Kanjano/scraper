import logging
from bs4 import BeautifulSoup
import time
from browser_manager import BrowserManager

# Configurazione logging: SOLO messaggio finale
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def cerca_rrguitars(prodotto):
    query = prodotto.replace(" ", "+")
    url = f"https://www.rrguitars.it/search?q={query}"

    driver = BrowserManager.create_driver()
    if not driver:
        return []

    risultati = []
    try:
        driver.get(url)
        time.sleep(5)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # 💡 Fix corretto: I prodotti sono dentro elementi <li class="product">
        prodotti = soup.select("li.product")

        for p in prodotti:
            try:
                nome_tag = p.select_one("h2.woocommerce-loop-product__title")
                prezzo_tag = p.select_one("span.woocommerce-Price-amount")
                link_tag = p.select_one("a")
                immagine_tag = p.select_one("img")

                nome = nome_tag.text.strip() if nome_tag else "N/A"
                prezzo = prezzo_tag.text.strip() if prezzo_tag else "N/A"
                link = link_tag["href"] if link_tag and link_tag.has_attr('href') else "#"
                immagine = immagine_tag["src"] if immagine_tag and immagine_tag.has_attr('src') else "N/A"

                risultati.append({
                    "nome": nome,
                    "prezzo": prezzo,
                    "link": link,
                    "immagine": immagine,
                    "sito": "RR Guitars"
                })
            except Exception:
                continue
    except Exception as e:
        logging.error(f"⚠️ Errore RR Guitars: {e}")
    finally:
        BrowserManager.close_driver(driver)

    logging.info(f"✅ Estrazione completata con {len(risultati)} risultati.")
    return risultati

def main():
    prodotto = input("🔎 Cosa vuoi cercare su RR Guitars? ")
    risultati = cerca_rrguitars(prodotto)

if __name__ == "__main__":
    main()