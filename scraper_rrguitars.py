import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time

# Configurazione del logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    logging.debug("Inizializzazione del driver Chrome.")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def cerca_rrguitars(prodotto):
    query = prodotto.replace(" ", "+")
    url = f"https://www.rrguitars.it/?s={query}&post_type=product"
    logging.debug(f"🌐 URL di ricerca per '{prodotto}': {url}")

    driver = setup_driver()
    driver.get(url)
    
    # Attendere che la pagina carichi completamente
    time.sleep(5)
    
    soup = BeautifulSoup(driver.page_source, "html.parser")
    risultati = []

    prodotti = soup.select(".product")
    logging.debug(f"Trovati {len(prodotti)} prodotti sulla pagina.")
    
    for p in prodotti:
        try:
            nome = p.select_one(".woocommerce-loop-product__title").text.strip()
            prezzo = p.select_one(".woocommerce-Price-amount").text.strip()
            link = p.select_one("a").get("href")
            immagine = p.select_one("img").get("src")

            logging.debug(f"Prodotto trovato: {nome} - Prezzo: {prezzo} - Link: {link} - Immagine: {immagine}")

            risultati.append({
                "nome": nome,
                "prezzo": prezzo,
                "link": link,
                "immagine": immagine,
                "sito": "RR Guitars"
            })
        except Exception as e:
            logging.error(f"Errore nell'estrazione di un prodotto: {e}")
            continue

    driver.quit()
    logging.debug(f"Estrazione completata con {len(risultati)} risultati.")
    return risultati

def log_risultati(risultati):
    if len(risultati) == 0:
        logging.info("Nessun prodotto trovato.")
    else:
        logging.info("Prodotti trovati:")
        for r in risultati:
            logging.info(f"📦 {r['nome']} - 💶 {r['prezzo']} - 🔗 {r['link']} - 🖼️ {r['immagine']}")

def main():
    prodotto = input("🔎 Cosa vuoi cercare su RR Guitars? ")
    risultati = cerca_rrguitars(prodotto)
    log_risultati(risultati)

if __name__ == "__main__":
    main()
