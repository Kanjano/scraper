import time
import re
from bs4 import BeautifulSoup
import undetected_chromedriver as uc

def setup_driver():
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    return uc.Chrome(options=options)

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

            img_tag = card.select_one("img")
            immagine = "N/A"
            if img_tag:
                immagine = img_tag.get("src") or img_tag.get("data-src") or "N/A"
                if immagine and not immagine.startswith("http"):
                    immagine = "https://www.tomassone.it" + immagine

            risultati.append({
                "nome": nome,
                "prezzo": f"€{round(prezzo_num, 2)}",
                "prezzo_numerico": round(prezzo_num, 2),
                "link": link,
                "immagine": immagine,
                "sito": "Tomassone"
            })
        except Exception as e:
            print(f"⚠️ Errore parsing prodotto: {e}")
            continue

    print(f"\n📦 Totale prodotti trovati su Tomassone: {len(risultati)}")
    return risultati
