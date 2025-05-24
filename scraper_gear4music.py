import re
import json
import time
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from multiprocessing import Pool

def setup_driver():
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    return uc.Chrome(options=options)

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

    driver = setup_driver()
    driver.get(url)

    for i in range(5):
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight / 5);")
        time.sleep(2)

    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    risultati = []

    match = re.search(r"window\.analyticsVariable\s*=\s*(\{.*?\});", html, re.DOTALL)
    if not match:
        print("❌ analyticsVariable non trovato.")
        driver.quit()
        return []

    try:
        js_raw = match.group(1)
        js_clean = re.sub(r",\s*([}\]])", r"\1", js_raw)
        data = json.loads(js_clean)
        products = data.get("products", [])

        for p in products:
            if isinstance(p, list):
                item = p[1]
                nome = item.get("name", "N/A").strip()
                nome_lower = nome.lower()

                if not all(k in nome_lower for k in parole_chiave):
                    continue

                price_gbp = float(item.get("price", 0))
                price_eur = round(price_gbp * 1.17, 2)

                a_tag = soup.find("a", title=nome)
                link = "N/A"
                immagine = "N/A"

                if a_tag:
                    href = a_tag.get("href", "")
                    if href:
                        link = "https://www.gear4music.it" + href
                        immagine = estrai_immagine_prodotto(driver, link)

                risultati.append({
                    "nome": nome,
                    "prezzo": f"€ {price_eur}",
                    "prezzo_numerico": price_eur,
                    "link": link,
                    "immagine": immagine,
                    "sito": "Gear4music"
                })

        return risultati

    except Exception as e:
        print(f"❌ Errore parsing Gear4music: {e}")
        return []
    finally:
        driver.quit()

def cerca_multiprodotti(lista_prodotti, num_processi=4):
    with Pool(processes=num_processi) as pool:
        risultati_totali = pool.map(cerca_gear4music, lista_prodotti)

    # Flatten dei risultati (ogni item è una lista)
    flat = [item for sublist in risultati_totali for item in sublist]
    print(f"\n✅ Totale prodotti trovati: {len(flat)}")
    return flat