import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from browser_manager import BrowserManager

def estrai_float_prezzo(prezzo_str):
    try:
        return float(prezzo_str.replace("€", "").replace(",", ".").strip())
    except:
        return 0

def cerca_thomann(prodotto):
    query = prodotto.replace(" ", "+")
    url = f"https://www.thomann.de/it/search_dir.html?sw={query}&smcs=123"
    print(f"\n🌐 Carico pagina Thomann: {url}")

    driver = BrowserManager.create_driver()
    if not driver:
        return []

    risultati = []
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".fx-product-list-entry"))
        )
        time.sleep(2)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        items = soup.select(".fx-product-list-entry")
        print(f"🟣 Trovati {len(items)} risultati su Thomann")

        for item in items:
            nome_el = item.select_one(".product__title")
            nome = nome_el.get_text(strip=True) if nome_el else "N/A"

            link_el = item.find("a", href=True)
            link = urljoin("https://www.thomann.de", link_el["href"]) if link_el else "N/A"

            immagine = "N/A"
            picture = item.select_one("picture")
            if picture:
                source = picture.find("source")
                if source:
                    immagine = source.get("data-srcset") or source.get("srcset", "N/A")
                if immagine == "N/A":
                    img = picture.find("img")
                    if img and img.has_attr("src") and "placeholder" not in img["src"]:
                        immagine = img["src"]

            prezzo_el = (
                item.select_one(".product__price-primary") or
                item.select_one(".fx-price-group__primary") or
                item.select_one(".price")
            )
            prezzo = prezzo_el.get_text(strip=True) if prezzo_el else "N/A"
            prezzo_numerico = estrai_float_prezzo(prezzo)

            risultati.append({
                "nome": nome,
                "prezzo": prezzo,
                "prezzo_numerico": prezzo_numerico,
                "link": link,
                "immagine": immagine,
                "sito": "Thomann"
            })
    except Exception as e:
        print(f"⚠️ Errore Thomann: {e}")
    finally:
        BrowserManager.close_driver(driver)

    return sorted(risultati, key=lambda x: x["prezzo_numerico"], reverse=True)

# Test manuale se lanciato direttamente
if __name__ == "__main__":
    prodotto = input("🔍 Prodotto da cercare su Thomann: ")
    risultati = cerca_thomann(prodotto)
    for r in risultati:
        print(f"[Thomann] {r['nome']} - {r['prezzo']} - {r['link']}")