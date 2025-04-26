import time
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def setup_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def cerca_centrochitarre(prodotto):
    query = prodotto.replace(" ", "+")
    url = f"https://www.centrochitarre.com/catalogsearch/result/?q={query}"

    print(f"\n🌐 Centro Chitarre: {url}")

    driver = setup_driver()
    driver.get(url)

    try:
        # Attendi che i prodotti si carichino (max 10 secondi)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".product-item"))
        )
        time.sleep(2)

        prodotti = driver.find_elements(By.CSS_SELECTOR, ".product-item")
        print(f"🔎 Trovati {len(prodotti)} prodotti nel DOM.")

        risultati = []

        for prodotto in prodotti:
            try:
                nome = prodotto.find_element(By.CSS_SELECTOR, ".product-item-link").text.strip()
                link = prodotto.find_element(By.CSS_SELECTOR, ".product-item-link").get_attribute("href")
                prezzo_text = prodotto.find_element(By.CSS_SELECTOR, ".price").text.strip()
                immagine_tag = prodotto.find_element(By.CSS_SELECTOR, "img")
                immagine = immagine_tag.get_attribute("src")

                prezzo_clean = re.sub(r"[^0-9,.]", "", prezzo_text).replace(",", ".")
                prezzo_eur = round(float(prezzo_clean), 2)

                print(f"\n🟢 Prodotto trovato:")
                print(f"   📛 Nome: {nome}")
                print(f"   💶 Prezzo: €{prezzo_eur}")
                print(f"   🔗 Link: {link}")
                print(f"   🖼️ Immagine: {immagine}")

                risultati.append({
                    "nome": nome,
                    "prezzo": f"€ {prezzo_eur}",
                    "prezzo_numerico": prezzo_eur,
                    "immagine": immagine,
                    "link": link,
                    "sito": "Centro Chitarre"
                })

            except Exception as e:
                print(f"⚠️ Errore parsing prodotto: {e}")

        return risultati

    except Exception as e:
        print(f"❌ Errore scraping Centro Chitarre: {e}")
        return []

    finally:
        driver.quit()
