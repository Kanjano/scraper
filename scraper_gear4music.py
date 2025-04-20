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

    for i in range(5):
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight / 5);")
        print(f"🕒 Scroll step {i+1}")
        time.sleep(2)

    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    print("✅ HTML ricevuto. Inizio parsing...")
    driver.quit()

    # Estrai i prodotti dal blocco JavaScript analyticsVariable
    script = soup.find("script", string=re.compile("analyticsVariable"))
    if not script:
        print("❌ analyticsVariable non trovato.")
        return []

    match = re.search(r"window\.analyticsVariable\s*=\s*(\{.*?\});", script.string, re.DOTALL)
    if not match:
        print("❌ Blocco JSON analyticsVariable non trovato.")
        return []

    data = json.loads(re.sub(r",\s*([}\]])", r"\1", match.group(1)))
    prodotti = data.get("products", [])
    risultati = []

    # Estrai blocco dataLayer per info prodotto aggiuntive (immagine, link)
    dataLayer_match = re.search(r"dataLayer\s*=\s*(\[\{.*?\}\]);", html, re.DOTALL)
    image_map = {}
    link_map = {}

    if dataLayer_match:
        try:
            dataLayer = json.loads(dataLayer_match.group(1))
            product_info = dataLayer[0].get("product", {})
            image_map[str(product_info.get("id"))] = product_info.get("primary_image_url", "N/A")
            link_map[str(product_info.get("id"))] = "https://www.gear4music.it" + product_info.get("url", "")
        except Exception as e:
            print(f"⚠️ Errore parsing dataLayer: {e}")

    for prod in prodotti:
        if isinstance(prod, list):
            item = prod[1]
            prod_id = str(item.get("id", ""))
            nome = item.get("name", "N/A")
            nome_lower = nome.lower()

            if not all(p in nome_lower for p in parole_chiave):
                continue

            try:
                price_gbp = float(item.get("price", 0))
                price_eur = round(price_gbp * 1.17, 2)
            except:
                price_eur = "N/A"

            risultati.append({
                "nome": nome,
                "prezzo": f"€ {price_eur}" if isinstance(price_eur, float) else "N/A",
                "prezzo_numerico": price_eur if isinstance(price_eur, float) else 0,
                "link": link_map.get(prod_id, "N/A"),
                "immagine": image_map.get(prod_id, "N/A"),
                "sito": "Gear4music"
            })

    print(f"✅ Risultati finali Gear4Music: {len(risultati)}")
    for r in risultati:
        print(f"🟢 {r['nome']}\n   💶 Prezzo: {r['prezzo']}\n   🔗 Link: {r['link']}\n   🖼️ Immagine: {r['immagine']}\n")

    return risultati

if __name__ == "__main__":
    prodotto = input("🔍 Cerca su Gear4Music: ")
    risultati = cerca_gear4music(prodotto)
    for r in risultati:
        print(f"[Gear4music] {r['nome']} - {r['prezzo']} - {r['link']}")