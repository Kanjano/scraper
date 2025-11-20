"""
Script di test per verificare il funzionamento del sistema di referral basato su database.
"""

from referral_db_manager import ReferralDBManager

def test_referral_db():
    """
    Testa il funzionamento del sistema di referral basato su database.
    """
    print("\n=== TEST SISTEMA REFERRAL BASATO SU DATABASE ===")
    
    # Registra lo stato del sistema di referral
    ReferralDBManager.log_referral_status()
    
    # Aggiungi alcuni link di test al database
    print("\n--- Aggiunta di link di test al database ---")
    
    test_links = [
        {
            "original_url": "https://www.thomann.de/it/fender_stratocaster.htm",
            "referral_url": "https://www.thomann.de/it/fender_stratocaster.htm?partner_id=INSTRINDER123",
            "store": "Thomann"
        },
        {
            "original_url": "https://www.thomann.de/it/gibson_les_paul.htm",
            "referral_url": "https://www.thomann.de/it/gibson_les_paul.htm?partner_id=INSTRINDER123",
            "store": "Thomann"
        },
        {
            "original_url": "https://www.andertons.co.uk/guitar-dept/electric-guitars/stratocaster/fender-player-stratocaster",
            "referral_url": "https://www.andertons.co.uk/guitar-dept/electric-guitars/stratocaster/fender-player-stratocaster?aff=INSTRINDER",
            "store": "Andertons"
        }
    ]
    
    for link in test_links:
        success = ReferralDBManager.add_referral_link(
            link["original_url"],
            link["referral_url"],
            link["store"]
        )
        status = "✅ Aggiunto" if success else "❌ Fallito"
        print(f"{status}: {link['store']} - {link['original_url']}")
    
    # Test di ricerca
    print("\n--- Test di ricerca referral ---")
    
    # Configura gli store attivi per il test
    ReferralDBManager.STORE_CONFIG["Thomann"] = True
    ReferralDBManager.STORE_CONFIG["Andertons"] = False  # Disabilitato
    
    test_urls = [
        # URL che dovrebbe trovare un match (Thomann è abilitato)
        "https://www.thomann.de/it/fender_stratocaster.htm",
        # URL che non dovrebbe trovare un match (Andertons è disabilitato)
        "https://www.andertons.co.uk/guitar-dept/electric-guitars/stratocaster/fender-player-stratocaster",
        # URL che non è nel database
        "https://www.thomann.de/it/ibanez_rg.htm",
        # URL di un altro store non configurato
        "https://www.gear4music.com/Guitar-and-Bass/Fender-Player-Stratocaster-MN-3-Tone-Sunburst/2SOH"
    ]
    
    for url in test_urls:
        original_url = url
        referral_url = ReferralDBManager.get_referral_link(url)
        
        if original_url != referral_url:
            print(f"✅ Referral trovato:")
            print(f"   Original: {original_url}")
            print(f"   Referral: {referral_url}")
        else:
            store = ReferralDBManager._get_store_from_url(url) or "Sconosciuto"
            print(f"❌ Nessun referral trovato per {store}:")
            print(f"   URL: {url}")
        print()
    
    # Mostra statistiche finali
    print("\n--- Statistiche finali ---")
    print(f"Totale link nel database: {len(ReferralDBManager._referral_db)}")

if __name__ == "__main__":
    test_referral_db()
