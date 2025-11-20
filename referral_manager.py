"""
Modulo per la gestione dei referral link per i vari store.
Centralizza la logica di trasformazione dei link in link di affiliazione.
"""

import logging
import os
from datetime import datetime

# Configurazione del logger
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, f'referral_{datetime.now().strftime("%Y%m%d")}.log')

# Configura il logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()  # Output anche su console
    ]
)

logger = logging.getLogger('referral_manager')

class ReferralManager:
    # Flag globale per abilitare/disabilitare tutto il sistema di referral
    REFERRAL_SYSTEM_ENABLED = True
    
    # Dizionario che mappa i nomi dei siti ai loro parametri di referral
    # Imposta ENABLED = False per i negozi senza referral
    REFERRAL_PARAMS = {
        "Thomann": {
            "enabled": True,  # Abilitato solo per Thomann
            "base_url": "https://www.thomann.de",
            "param_name": "partner_id",
            "param_value": "INSTRINDER123",  # ID di test per Thomann
            "append_method": "query"  # Metodo per aggiungere il referral: query, path, replace
        },
        "Andertons": {
            "enabled": False,  # Disabilitato
            "base_url": "https://www.andertons.co.uk",
            "param_name": "aff",
            "param_value": "YOUR_ANDERTONS_AFFILIATE_ID",
            "append_method": "query"
        },
        "Gear4music": {
            "enabled": False,  # Disabilitato
            "base_url": "https://www.gear4music.com",
            "param_name": "affiliate",
            "param_value": "YOUR_GEAR4MUSIC_AFFILIATE_ID",
            "append_method": "query"
        },
        "Musik Produktiv": {
            "enabled": False,  # Disabilitato
            "base_url": "https://www.musik-produktiv.com",
            "param_name": "ref",
            "param_value": "YOUR_MUSIK_PRODUKTIV_REF_ID",
            "append_method": "query"
        },
        "Strumenti Musicali": {
            "enabled": False,  # Disabilitato
            "base_url": "https://www.strumentimusicali.net",
            "param_name": "affiliate_id",
            "param_value": "YOUR_STRUMENTIMUSICALI_AFFILIATE_ID",
            "append_method": "query"
        },
        "Centro Chitarre": {
            "enabled": False,  # Disabilitato
            "base_url": "https://www.centrochitarre.com",
            "param_name": "ref",
            "param_value": "YOUR_CENTROCHITARRE_REF_ID",
            "append_method": "query"
        },
        "Tomassone": {
            "enabled": False,  # Disabilitato
            "base_url": "https://www.thomassone.fr",
            "param_name": "aff",
            "param_value": "YOUR_TOMASSONE_AFFILIATE_ID",
            "append_method": "query"
        }
    }

    @staticmethod
    def log_referral_status():
        """
        Registra lo stato del sistema di referral all'avvio dell'applicazione.
        Mostra quali negozi hanno il referral attivo e quali no.
        """
        if not ReferralManager.REFERRAL_SYSTEM_ENABLED:
            logger.info("🔴 Sistema di referral DISABILITATO globalmente")
            return
            
        logger.info("🟢 Sistema di referral ATTIVO")
        logger.info("Status dei referral per negozio:")
        
        for site_name, params in ReferralManager.REFERRAL_PARAMS.items():
            enabled = params.get("enabled", False)
            has_valid_id = not params.get("param_value", "").startswith("YOUR_")
            
            if enabled and has_valid_id:
                status = "✅ ATTIVO"
            elif enabled and not has_valid_id:
                status = "⚠️ CONFIGURAZIONE INCOMPLETA (ID mancante)"
            else:
                status = "❌ DISABILITATO"
                
            logger.info(f"  - {site_name}: {status}")
    
    @staticmethod
    def add_referral(url, site_name):
        """
        Aggiunge i parametri di referral a un URL in base al sito.
        
        Args:
            url (str): L'URL originale del prodotto
            site_name (str): Il nome del sito (es. "Thomann", "Andertons")
            
        Returns:
            str: L'URL con i parametri di referral aggiunti se disponibile, altrimenti l'URL originale
        """
        # Verifica se il sistema di referral è abilitato globalmente
        if not ReferralManager.REFERRAL_SYSTEM_ENABLED:
            return url
            
        # Gestione dei casi di errore
        if not url or url == "N/A":
            return url
            
        # Verifica se il sito è presente nella configurazione
        if site_name not in ReferralManager.REFERRAL_PARAMS:
            logger.warning(f"⚠️ Nessuna configurazione referral trovata per il sito: {site_name}")
            return url
            
        params = ReferralManager.REFERRAL_PARAMS[site_name]
        
        # Verifica se il referral è abilitato per questo sito
        if not params.get("enabled", False):
            logger.debug(f"Referral disabilitato per {site_name}")
            return url
            
        # Verifica se l'ID referral è stato configurato correttamente
        if params.get("param_value", "").startswith("YOUR_"):
            logger.warning(f"⚠️ ID referral non configurato per {site_name}")
            return url
            
        # Verifica se l'URL appartiene al dominio corretto
        if params["base_url"] not in url:
            logger.debug(f"URL non appartiene al dominio {params['base_url']}: {url}")
            return url
            
        try:
            new_url = url
            # Metodo di aggiunta del referral
            if params["append_method"] == "query":
                # Aggiungi il parametro come query string
                separator = "&" if "?" in url else "?"
                new_url = f"{url}{separator}{params['param_name']}={params['param_value']}"
                
            elif params["append_method"] == "path":
                # Aggiungi il parametro come parte del percorso
                new_url = f"{url}/{params['param_name']}/{params['param_value']}"
                
            elif params["append_method"] == "replace":
                # Sostituisci un pattern nell'URL
                # Questo metodo è per siti che richiedono una struttura specifica
                new_url = url.replace(params["base_url"], f"{params['base_url']}/{params['param_name']}/{params['param_value']}")
                
            # Registra la trasformazione del link
            if new_url != url:
                logger.info(f"✅ Referral aggiunto per {site_name}: {url} -> {new_url}")
            
            return new_url
            
        except Exception as e:
            logger.error(f"❌ Errore durante l'aggiunta del referral per {site_name}: {str(e)}")
            return url
            
        return url
