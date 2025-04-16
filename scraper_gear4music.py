import re
import json
import time
from bs4 import BeautifulSoup
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

def cerca_gear4music(prodotto):
    query = prodotto.replace(" ", "+")
    parole_chiave = [p.lower() for p in prodotto.split()]
    url = f"https://www.gear4music.it/it/search/?str_search_phrase={query}"
    print(f"\n🌐 Gear4Music: {url}")

    driver = setup_driver()
    driver.get(url)

    # Scroll dinamico per caricare tutti i prodotti
    for i in range(5):
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight / 5);")
        print(f"🕒 Attendo caricamento contenuti... round {i+1}")
        time.sleep(3)

    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    driver.quit()

    risultati = []

    # 🔍 Mappiamo gli ID prodotto con immagine e link reali dal DOM
    image_map = {}
    link_map = {}
    for card in soup.select(".df-card-product"):
        link_el = card.select_one("a[href*='/product/']")
        img_el = card.select_one("img")

        if link_el and img_el:
            href = link_el.get("href", "")
            prod_id = href.split("/")[-1]
            full_link = "https://www.gear4music.it" + href
            image_url = img_el.get("src", "N/A")
            image_map[prod_id] = image_url
            link_map[prod_id] = full_link

    # 🧠 Analisi dati JS (analyticsVariable) per nome e prezzo
    match = re.search(r"window\.analyticsVariable\s*=\s*(\{.*?\});", html, re.DOTALL)
    if not match:
        print("⚠ Blocco dati JS non trovato.")
        return []

    try:
        data_js = re.sub(r",\s*([}\]])", r"\1", match.group(1))  # trailing commas
        data = json.loads(data_js)
        products = data.get("products", [])

        for prod in products:
            if isinstance(prod, list):
                item = prod[1]
                prod_id = str(item.get("id", ""))
                nome = item.get("name", "N/A")
                nome_lower = nome.lower()

                # ✅ FILTRO parole chiave
                if not all(p in nome_lower for p in parole_chiave):
                    continue

                price_gbp = float(item.get("price", 0))
                price_eur = round(price_gbp * 1.17, 2)

                risultati.append({
                    "nome": nome,
                    "prezzo": f"€ {price_eur}",
                    "prezzo_numerico": price_eur,
                    "link": link_map.get(prod_id, f"https://www.gear4music.it/it/product/{prod_id}"),
                    "immagine": image_map.get(prod_id, "N/A"),
                    "sito": "Gear4music"
                })

        print(f"📦 Gear4Music risultati trovati: {len(risultati)}")

    except Exception as e:
        print(f"❌ Errore parsing Gear4music: {e}")

    return risultati