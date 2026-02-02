from bs4 import BeautifulSoup
import time
from browser_manager import BrowserManager

def cerca_ginomusica(prodotto):
    query = prodotto.replace(" ", "+")
    # URL aggiornato
    url = f"https://www.ginomusica.it/it/advanced_search_result.html?search_in_description=0&keyword={query}"
    print(f"🌐 Gino Musica: {url}")

    driver = BrowserManager.create_driver()
    if not driver:
        return []

    risultati = []
    try:
        driver.get(url)
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        # Parsing dei risultati
        prodotti = soup.select(".productListingDivRow")
        
        for p in prodotti:
            try:
                # Link e Nome
                link_elem = p.select_one("a")
                if not link_elem:
                    continue
                link = link_elem.get("href")
                
                # Il nome è spesso nel title dell'immagine o nel testo del link
                img_elem = p.select_one("img.listingProductImage")
                if img_elem:
                    nome = img_elem.get("alt") or img_elem.get("title")
                    immagine = img_elem.get("src")
                    if immagine and not immagine.startswith("http"):
                        immagine = "https://www.ginomusica.it/" + immagine.lstrip("/")
                else:
                    nome = link_elem.text.strip()
                    immagine = "N/A"

                # Prezzo - cerchiamo nel testo o in un elemento fratello
                # Nel dump non si vede chiaramente il prezzo, ma di solito è in un div separato o span
                # Proviamo a cercare un prezzo nel testo del div row
                text_content = p.get_text(strip=True)
                # Cerchiamo un pattern prezzo € 1.234,56
                import re
                price_match = re.search(r"€\s*[\d\.,]+", text_content)
                prezzo = price_match.group(0) if price_match else "Vedi sito"

                risultati.append({
                    "nome": nome,
                    "prezzo": prezzo,
                    "link": link,
                    "immagine": immagine,
                    "sito": "Gino Musica"
                })
            except Exception as e:
                # print(f"Errore parsing prodotto: {e}")
                continue
    except Exception as e:
        print(f"⚠️ Errore Gino Musica: {e}")
    finally:
        if not risultati and driver:
            print("⚠️ Nessun risultato trovato. Salvataggio HTML per debug...")
            try:
                with open("ginomusica_dump.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
            except:
                pass
        BrowserManager.close_driver(driver)

    return risultati

def main():
    prodotto = input("🔎 Cosa vuoi cercare su Gino Musica? ")
    risultati = cerca_ginomusica(prodotto)
    for r in risultati:
        print(f"\n📦 {r['nome']}\n💶 {r['prezzo']}\n🔗 {r['link']}\n🖼️ {r['immagine']}")

if __name__ == "__main__":
    main()