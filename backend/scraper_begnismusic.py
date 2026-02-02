from bs4 import BeautifulSoup
import time
from browser_manager import BrowserManager

def cerca_begnismusic(prodotto):
    query = prodotto.replace(" ", "+")
    url = f"https://www.begnismusic.com/it/ricerca?controller=search&search_query={query}"
    print(f"🌐 Begnismusic: {url}")

    driver = BrowserManager.create_driver()
    if not driver:
        return []

    risultati = []
    try:
        driver.get(url)
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "html.parser")

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
    except Exception as e:
        print(f"⚠️ Errore Begnismusic: {e}")
    finally:
        BrowserManager.close_driver(driver)

    return risultati

def main():
    prodotto = input("🔎 Cosa vuoi cercare su Begnismusic? ")
    risultati = cerca_begnismusic(prodotto)
    for r in risultati:
        print(f"\n📦 {r['nome']}\n💶 {r['prezzo']}\n🔗 {r['link']}\n🖼️ {r['immagine']}")

if __name__ == "__main__":
    main()