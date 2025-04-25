import requests
from bs4 import BeautifulSoup
import json
import re

def cerca_centrochitarre(prodotto):
    query = prodotto.replace(" ", "+")
    url = f"https://www.centrochitarre.com/catalogsearch/result/?q={query}"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    script_tags = soup.find_all("script", type="application/ld+json")
    risultati = []

    for script in script_tags:
        try:
            data = json.loads(script.string.strip())
            if isinstance(data, list):
                for item in data:
                    if item.get("@type") == "Product":
                        nome = item.get("name", "N/A")
                        prezzo = item.get("offers", [{}])[0].get("price", "N/A")
                        link = item.get("url", "")
                        immagine = item.get("image", "")

                        try:
                            prezzo_numerico = float(prezzo)
                        except:
                            prezzo_numerico = 0

                        risultati.append({
                            "nome": nome,
                            "prezzo": f"€ {prezzo}",
                            "prezzo_numerico": prezzo_numerico,
                            "immagine": immagine,
                            "link": link,
                            "sito": "Centro Chitarre"
                        })
            elif isinstance(data, dict) and data.get("@type") == "Product":
                nome = data.get("name", "N/A")
                prezzo = data.get("offers", [{}])[0].get("price", "N/A")
                link = data.get("url", "")
                immagine = data.get("image", "")

                try:
                    prezzo_numerico = float(prezzo)
                except:
                    prezzo_numerico = 0

                risultati.append({
                    "nome": nome,
                    "prezzo": f"€ {prezzo}",
                    "prezzo_numerico": prezzo_numerico,
                    "immagine": immagine,
                    "link": link,
                    "sito": "Centro Chitarre"
                })
        except Exception as e:
            continue

    return risultati