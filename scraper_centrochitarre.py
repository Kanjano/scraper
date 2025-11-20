import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from browser_manager import BrowserManager

def safe_find_element(parent, by, selector):
    try:
        return parent.find_element(by, selector)
    except:
        return None

def cerca_centrochitarre(prodotto):
    query = prodotto.replace(" ", "+")
    url = f"https://www.centrochitarre.com/catalogsearch/result/?q={query}"

    driver = BrowserManager.create_driver()
    if not driver:
        return []

    risultati = []

    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".product-item"))
        )
        time.sleep(2)

        prodotti = driver.find_elements(By.CSS_SELECTOR, ".product-item")

        for prodotto in prodotti:
            try:
                nome_element = safe_find_element(prodotto, By.CSS_SELECTOR, ".product-item-link")
                link_element = nome_element
                prezzo_element = safe_find_element(prodotto, By.CSS_SELECTOR, ".price")
                immagine_element = safe_find_element(prodotto, By.CSS_SELECTOR, "img")

                # Skippa se manca nome, link o prezzo
                if not nome_element or not link_element or not prezzo_element:
                    continue

                nome = nome_element.text.strip()
                link = link_element.get_attribute("href")
                immagine = immagine_element.get_attribute("src") if immagine_element else None

                prezzo_text = prezzo_element.text.strip()
                prezzo_clean = re.sub(r"[^\d,\.]", "", prezzo_text)
                if '.' in prezzo_clean and ',' in prezzo_clean:
                    prezzo_clean = prezzo_clean.replace('.', '').replace(',', '.')
                elif ',' in prezzo_clean:
                    prezzo_clean = prezzo_clean.replace(',', '.')

                prezzo_eur = round(float(prezzo_clean), 2)
                prezzo_display = f"€ {prezzo_eur}"

                risultati.append({
                    "nome": nome,
                    "prezzo": prezzo_display,
                    "prezzo_numerico": prezzo_eur,
                    "immagine": immagine,
                    "link": link,
                    "sito": "Centro Chitarre"
                })

            except Exception:
                continue  # Ignora eventuali errori su singoli prodotti

    except Exception as e:
        print(f"⚠️ Errore Centro Chitarre: {e}")

    finally:
        BrowserManager.close_driver(driver)

    return risultati

if __name__ == "__main__":
    prodotto = input("🔎 Prodotto da cercare su Centro Chitarre: ")
    risultati = cerca_centrochitarre(prodotto)
    for r in risultati:
        print(f"[Centro Chitarre] {r['nome']} - {r['prezzo']} - {r['link']}")
