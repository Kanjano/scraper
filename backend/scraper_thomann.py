import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}


def estrai_float_prezzo(prezzo_str):
    try:
        return float(prezzo_str.replace("€", "").replace(",", ".").strip())
    except:
        return 0


def cerca_thomann(prodotto):
    query = prodotto.replace(" ", "+")
    url = f"https://www.thomann.de/it/search_dir.html?sw={query}&smcs=123"
    print(f"\n🌐 Carico pagina Thomann: {url}")

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        html = resp.text
    except requests.RequestException as exc:
        raise RuntimeError(f"Thomann: HTTP request failed — {exc}") from exc

    risultati = []
    soup = BeautifulSoup(html, "html.parser")

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

        # Estrazione prezzo originale (se presente)
        prezzo_originale_el = (
            item.select_one(".product__price-secondary") or
            item.select_one(".fx-price-group__secondary") or
            item.select_one(".price--original") or
            item.select_one("del") or
            item.select_one(".product__price-original")
        )
        prezzo_originale = prezzo_originale_el.get_text(strip=True) if prezzo_originale_el else "N/A"
        prezzo_originale_numerico = estrai_float_prezzo(prezzo_originale)

        # Se non c'è prezzo originale o è 0, usa il prezzo attuale come base (nessuno sconto)
        if prezzo_originale_numerico == 0:
            prezzo_originale_numerico = prezzo_numerico

        risultati.append({
            "nome": nome,
            "prezzo": prezzo,
            "prezzo_numerico": prezzo_numerico,
            "prezzo_originale": prezzo_originale,
            "prezzo_originale_numerico": prezzo_originale_numerico,
            "link": link,
            "immagine": immagine,
            "sito": "Thomann"
        })

    return sorted(risultati, key=lambda x: x["prezzo_numerico"], reverse=True)

# Test manuale se lanciato direttamente
if __name__ == "__main__":
    prodotto = input("🔍 Prodotto da cercare su Thomann: ")
    risultati = cerca_thomann(prodotto)
    for r in risultati:
        print(f"[Thomann] {r['nome']} - {r['prezzo']} - {r['link']}")
