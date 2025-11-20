from scraper_thomann import cerca_thomann
from scraper_musik_produktiv import cerca_musik_produktiv


def cerca_germania(prodotto):
    scraper_funzioni = [
        ("Musik Produktiv", cerca_musik_produktiv),
        ("Thomann", cerca_thomann)
    ]

    risultati = []

    for nome_sito, scraper in scraper_funzioni:
        try:
            print(f"\n Scraping {nome_sito}...")
            dati = scraper(prodotto)
            for r in dati:
                r["sito"] = nome_sito
            risultati.extend(dati)
        except Exception as e:
            print(f"❌ Errore da {nome_sito}: {e}")

    return risultati