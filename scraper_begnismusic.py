from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time

def setup_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def cerca_begnismusic(prodotto):
    query = prodotto.replace(" ", "+")
    url = f"https://www.begnismusic.com/it/ricerca?controller=search&search_query={query}"
    print(f"🌐 Begnismusic: {url}")

    driver = setup_driver()
    driver.get(url)
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    risultati = []

    prodotti = soup.select(".product-miniature")
    for p in prodotti:
        try:
            nome = p.select_one(".product-title").text.strip()
            prezzo = p.select_one(".price").text.strip()
            link = p.select_one("a").get("href")
            img_tag = p.select_one("img")
            immagine = img_tag.get("src") if img_tag else "N/A"

            risultati.append({
                "nome": nome,
                "prezzo": prezzo,
                "link": link,
                "immagine": immagine,
                "sito": "Begnismusic"
            })
        except Exception:
            continue

    driver.quit()
    return risultati

def main():
    prodotto = input("🔎 Cosa vuoi cercare su Begnismusic? ")
    risultati = cerca_begnismusic(prodotto)
    for r in risultati:
        print(f"\n📦 {r['nome']}\n💶 {r['prezzo']}\n🔗 {r['link']}\n🖼️ {r['immagine']}")

if __name__ == "__main__":
    main()