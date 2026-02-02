from bs4 import BeautifulSoup
import time
from browser_manager import BrowserManager

def cerca_luckymusic(prodotto):
    query = prodotto.replace(" ", "+")
    url = f"https://www.luckymusic.com/it/search?controller=search&s={query}"
    print(f"🌐 Lucky Music: {url}")

    driver = BrowserManager.create_driver()
    if not driver:
        return []

    risultati = []
    try:
        driver.get(url)
        time.sleep(3)
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        # Tentativo 1: Estrazione da dataLayer (più affidabile)
        import re
        import json
        
        match = re.search(r"let cdcDatalayer = ({.*?});", html, re.DOTALL)
        if match:
            try:
                json_str = match.group(1)
                # Debug: print first 100 chars
                print(f"DEBUG JSON: {json_str[:100]}...")
                data = json.loads(json_str)
                items = data.get("ecommerce", {}).get("items", [])
                
                for item in items:
                    nome = item.get("item_name", "N/A")
                    prezzo = item.get("price", "0")
                    
                    # Il link e l'immagine non sono direttamente nel dataLayer, 
                    # ma possiamo provare a trovarli nel DOM usando l'ID o il nome
                    # Oppure costruire il link se c'è un pattern, ma LuckyMusic usa ID-nome.html
                    
                    # Cerchiamo nel DOM l'elemento che corrisponde a questo prodotto
                    # Spesso i data-id o simili corrispondono
                    
                    # Fallback misto: dataLayer per prezzi/nomi, DOM per link/img
                    # Ma se il DOM non c'è, questo non aiuta.
                    # Guardando il dump, c'è anche <script type="application/ld+json"> con ItemList
                    pass
            except Exception as e:
                print(f"⚠️ Errore parsing JSON dataLayer: {e}")

        # Parsing DOM classico (aggiornato con selettori dal dump)
        prodotti = soup.select(".product-miniature")
        
        for p in prodotti:
            try:
                # Nome e Link
                title_elem = p.select_one(".product-title a")
                if not title_elem:
                    continue
                nome = title_elem.text.strip()
                link = title_elem.get("href")
                
                # Prezzo
                price_elem = p.select_one(".product-price")
                prezzo = price_elem.text.strip() if price_elem else "Vedi sito"
                
                # Immagine
                img_elem = p.select_one(".product-thumbnail img")
                if img_elem:
                    immagine = img_elem.get("data-src") or img_elem.get("src")
                else:
                    immagine = "N/A"

                risultati.append({
                    "nome": nome,
                    "prezzo": prezzo,
                    "link": link,
                    "immagine": immagine,
                    "sito": "Lucky Music"
                })
            except Exception as e:
                # print(f"Errore parsing prodotto: {e}")
                continue
                
        # Se abbiamo usato JSON-LD, proviamo ad arricchire i dati (prezzo) visitando i link o cercando meglio
        # Per ora ritorniamo quello che abbiamo
        
    except Exception as e:
        print(f"⚠️ Errore Lucky Music: {e}")
    finally:
        if not risultati and driver:
            print("⚠️ Nessun risultato trovato. Salvataggio HTML per debug...")
            try:
                with open("luckymusic_dump.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
            except:
                pass
        BrowserManager.close_driver(driver)

    return risultati

def main():
    prodotto = input("🔎 Cosa vuoi cercare su Lucky Music? ")
    risultati = cerca_luckymusic(prodotto)
    for r in risultati:
        print(f"\n📦 {r['nome']}\n💶 {r['prezzo']}\n🔗 {r['link']}\n🖼️ {r['immagine']}")

if __name__ == "__main__":
    main()