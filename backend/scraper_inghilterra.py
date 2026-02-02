from scraper_andertons import cerca_andertons
from scraper_gear4music import cerca_gear4music


def cerca_inghilterra(prodotto):
    scraper_funzioni = [
        ("Andertons", cerca_andertons),
        ("Gear4music", cerca_gear4music)
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