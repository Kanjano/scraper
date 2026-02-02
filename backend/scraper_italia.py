from scraper_tomassone import cerca_tomassone
from scraper_centrochitarre import cerca_centrochitarre


def cerca_italia(prodotto):
    scraper_funzioni = [
        ("Centro Chitarre", cerca_centrochitarre),
        ("Tomassone", cerca_tomassone)
    ]

    risultati = []

    for nome_sito, scraper in scraper_funzioni:
        try:
            print(f"\n🇮 Scraping {nome_sito}...")
            dati = scraper(prodotto)
            for r in dati:
                r["sito"] = nome_sito
            risultati.extend(dati)
        except Exception as e:
            print(f"❌ Errore da {nome_sito}: {e}")

    return risultati