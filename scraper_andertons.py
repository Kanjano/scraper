import re
import json
import time
import undetected_chromedriver as uc

def setup_driver():
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    return uc.Chrome(options=options)

def cerca_andertons(prodotto):
    query = prodotto.replace(" ", "+")
    url = f"https://www.andertons.co.uk/search.php?search_query={query}"

    driver = setup_driver()
    driver.get(url)
    time.sleep(5)

    html = driver.page_source
    match = re.search(r'BODL\s*=\s*JSON\.parse\(\s*"(.+?)"\s*\);', html, re.DOTALL)

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

                prezzo_raw = product.get("price", {}).get("with_tax", {})
                price_formatted = prezzo_raw.get("formatted", "N/A")
                prezzo_eur = "N/A"
                prezzo_numerico = 0

                if price_formatted != "N/A":
                    try:
                        price_clean = re.sub(r"[^\d.]", "", price_formatted)
                        price_float = float(price_clean)
                        prezzo_eur = round(price_float * 1.17, 2)
                        prezzo_numerico = prezzo_eur
                    except:
                        pass

                img_raw = product.get("image", {}).get("data", "")
                immagine = img_raw.replace("{:size}", "500x500") if img_raw else "N/A"

                risultati.append({
                    "nome": nome,
                    "prezzo": f"€ {prezzo_eur}" if prezzo_eur != "N/A" else "N/A",
                    "prezzo_numerico": prezzo_numerico,
                    "immagine": immagine,
                    "link": link,
                    "sito": "Andertons"
                })

        except:
            pass

    driver.quit()
    return risultati