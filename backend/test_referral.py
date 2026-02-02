"""
Script di test per verificare il funzionamento del sistema di referral.
"""

from referral_manager import ReferralManager

def test_referral_links():
    """
    Testa il funzionamento del sistema di referral con diversi URL.
    """
    print("\n=== TEST SISTEMA REFERRAL ===")
    
    # Registra lo stato del sistema di referral
    ReferralManager.log_referral_status()
    
    # Test con URL di diversi negozi
    test_urls = {
        "Thomann": "https://www.thomann.de/it/fender_stratocaster.htm",
        "Andertons": "https://www.andertons.co.uk/guitar-dept/electric-guitars/stratocaster/fender-player-stratocaster",
        "Gear4music": "https://www.gear4music.com/Guitar-and-Bass/Fender-Player-Stratocaster-MN-3-Tone-Sunburst/2SOH",
        "Musik Produktiv": "https://www.musik-produktiv.com/it/fender-player-stratocaster-mn-3ts.html",
        "Strumenti Musicali": "https://www.strumentimusicali.net/product_info.php/products_id/10867/fender-player-stratocaster-mn-3-color-sunburst.html",
    }
    
    print("\n--- Risultati del test ---")
    for site_name, url in test_urls.items():
        original_url = url
        modified_url = ReferralManager.add_referral(url, site_name)
        
        if original_url != modified_url:
            print(f"✅ {site_name}: Referral aggiunto")
            print(f"   Original: {original_url}")
            print(f"   Modified: {modified_url}")
        else:
            print(f"❌ {site_name}: Nessun referral aggiunto")
            print(f"   URL: {url}")
        print()

if __name__ == "__main__":
    test_referral_links()
