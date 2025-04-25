import time
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def setup_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def cerca_tomassone(prodotto):
    query = prodotto.replace(" ", "+")
    url = f"https://www.tomassone.it/ita/catalogsearch/result/?q={query}"
    print(f"\n🌐 Tomassone: {url}")

    driver = setup_driver()
    driver.get(url)
    time.sleep(3)
    html = driver.page_source
    driver.quit()

    soup = BeautifulSoup(html, "html.parser")
    risultati = []

    for card in soup.select(".product-item-info"):
        try:
            nome = card.select_one(".product-item-link").get_text(strip=True)
            link = card.select_one(".product-item-link").get("href", "").strip()
            prezzo_raw = card.select_one(".price").get_text(strip=True)
            prezzo_num = float(re.sub(r"[^\d,]", "", prezzo_raw).replace(",", "."))

            risultati.append({
                "nome": nome,
                "prezzo": f"€{round(prezzo_num, 2)}",
                "prezzo_numerico": round(prezzo_num, 2),
                "link": link,
                "immagine": "N/A",  # Non disponibile nelle SERP
                "sito": "Tomassone"
            })
        except Exception:
            continue

    return risultati