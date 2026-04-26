import re
import json
import time
from browser_manager import BrowserManager

def cerca_andertons(prodotto):
    query = prodotto.replace(" ", "+")
    url = f"https://www.andertons.co.uk/search.php?search_query={query}"

    driver = BrowserManager.create_driver()
    if not driver:
        return []

    risultati = []
    try:
        driver.get(url)
        time.sleep(5)

        html = driver.page_source
        match = re.search(r'BODL\s*=\s*JSON\.parse\(\s*"(.+?)"\s*\);', html, re.DOTALL)

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

                    # Estrazione prezzo originale (was_price)
                    prezzo_originale = "N/A"
                    prezzo_originale_numerico = prezzo_numerico # Default: nessun sconto

                    was_price_raw = product.get("price", {}).get("was_price", {})
                    was_price_formatted = was_price_raw.get("formatted", "N/A")
                    
                    if was_price_formatted != "N/A":
                        try:
                            was_price_clean = re.sub(r"[^\d.]", "", was_price_formatted)
                            was_price_float = float(was_price_clean)
                            # Se il prezzo originale è maggiore del prezzo attuale
                            if was_price_float > 0:
                                was_price_eur = round(was_price_float * 1.17, 2)
                                if was_price_eur > prezzo_numerico:
                                    prezzo_originale = f"€ {was_price_eur}"
                                    prezzo_originale_numerico = was_price_eur
                        except:
                            pass

                    risultati.append({
                        "nome": nome,
                        "prezzo": f"€ {prezzo_eur}" if prezzo_eur != "N/A" else "N/A",
                        "prezzo_numerico": prezzo_numerico,
                        "prezzo_originale": prezzo_originale,
                        "prezzo_originale_numerico": prezzo_originale_numerico,
                        "immagine": immagine,
                        "link": link,
                        "sito": "Andertons"
                    })

            except Exception:
                pass
    except Exception as e:
        print(f"⚠️ Errore Andertons: {e}")
        raise
    finally:
        BrowserManager.close_driver(driver)

    return risultati

if __name__ == "__main__":
    prodotto = input("🔎 Prodotto da cercare su Andertons: ")
    risultati = cerca_andertons(prodotto)
    for r in risultati:
        print(f"[Andertons] {r['nome']} - {r['prezzo']} - {r['link']}")