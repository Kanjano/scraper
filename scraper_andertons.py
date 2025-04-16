import re
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def setup_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def cerca_andertons(prodotto):
    query = prodotto.replace(" ", "+")
    url = f"https://www.andertons.co.uk/search.php?search_query={query}"
    print(f"\n🌐 Andertons: {url}")

    driver = setup_driver()
    driver.get(url)
    time.sleep(5)

    html = driver.page_source
    print("📄 HTML ricevuto, cerco `injectedContext`...")

    match = re.search(r'const injectedContext = JSON\.parse\("(.+?)"\);', html, re.DOTALL)

    risultati = []

    if match:
        raw_json = match.group(1)
        try:
            decoded_json = bytes(raw_json, "utf-8").decode("unicode_escape")
            data = json.loads(decoded_json)
            products = data.get("search", {}).get("products", [])

            for product in products:
                nome = product.get("name", "N/A")
                link = product.get("url", "N/A")

                # Prezzo
                prezzo_raw = product.get("price", {})
                price_formatted = prezzo_raw.get("formatted", "N/A")
                prezzo_eur = "N/A"
                prezzo_numerico = 0

                if price_formatted != "N/A":
                    try:
                        price_clean = price_formatted.replace("£", "").replace(",", "").strip()
                        price_float = float(price_clean)
                        prezzo_eur = round(price_float * 1.17, 2)
                        prezzo_numerico = prezzo_eur
                    except Exception as e:
                        print(f"⚠️ Errore parsing prezzo: {e}")

                # Immagine (sostituiamo {:size})
                img_raw = product.get("image", {}).get("data", "")
                if img_raw:
                    immagine = img_raw.replace("{:size}", "500x500")
                else:
                    immagine = "N/A"

                print(f"\n📦 Prodotto:")
                print(f"  🔸 Nome: {nome}")
                print(f"  🔸 Prezzo: {price_formatted} → € {prezzo_eur}")
                print(f"  🔸 Immagine: {immagine}")
                print(f"  🔸 Link: {link}")

                risultati.append({
                    "nome": nome,
                    "prezzo": f"€ {prezzo_eur}" if prezzo_eur != "N/A" else "N/A",
                    "prezzo_numerico": prezzo_numerico,
                    "immagine": immagine,
                    "link": link,
                    "sito": "Andertons"
                })

            print(f"\n✅ Totale risultati trovati su Andertons: {len(risultati)}")

        except Exception as e:
            print(f"❌ Errore nel parsing del JSON: {e}")
    else:
        print("⚠️ Blocco `injectedContext` non trovato.")

    driver.quit()
    return risultati