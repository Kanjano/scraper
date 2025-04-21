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
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def estrai_immagine_prodotto(link_prodotto):
    try:
        driver = setup_driver()
        driver.get(link_prodotto)
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        driver.quit()
        img_tag = soup.select_one("img.main-image[data-src]")
        if img_tag:
            return img_tag["data-src"]
    except Exception as e:
        print(f"❌ Errore estrazione immagine da {link_prodotto}: {e}")
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
        print(f"🕒 Scroll step {i + 1}")
        time.sleep(2)

    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    driver.quit()

    risultati = []

    match = re.search(r"window\.analyticsVariable\s*=\s*(\{.*?\});", html, re.DOTALL)
    if not match:
        print("❌ analyticsVariable non trovato.")
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

                # Cerca <a title="nome"> nel DOM
                a_tag = soup.find("a", title=nome)
                link = "N/A"
                immagine = "N/A"

                if a_tag:
                    href = a_tag.get("href", "")
                    if href:
                        link = "https://www.gear4music.it" + href
                        immagine = estrai_immagine_prodotto(link)

                print("\n🟢 Prodotto trovato:")
                print(f"   📛 Nome: {nome}")
                print(f"   💶 Prezzo EUR: €{price_eur}")
                print(f"   🔗 Link: {link}")
                print(f"   🖼️ Immagine: {immagine}")

                risultati.append({
                    "nome": nome,
                    "prezzo": f"€ {price_eur}",
                    "prezzo_numerico": price_eur,
                    "link": link,
                    "immagine": immagine,
                    "sito": "Gear4music"
                })

        print(f"\n📦 Gear4Music risultati totali: {len(risultati)}")
        return risultati

    except Exception as e:
        print(f"❌ Errore parsing Gear4music: {e}")
        return []