"""
Modulo per la gestione di un database di link referral predefiniti.
Questo approccio è utile quando vengono forniti link di referral completi
invece di un sistema per costruirli dinamicamente.
"""

import os
import json
import logging
from datetime import datetime
import re
from urllib.parse import urlparse

# Configurazione del logger
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, f'referral_db_{datetime.now().strftime("%Y%m%d")}.log')

# Configura il logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()  # Output anche su console
    ]
)

logger = logging.getLogger('referral_db_manager')

class ReferralDBManager:
    """
    Gestisce un database di link referral predefiniti.
    Il database è un dizionario che mappa gli URL originali ai loro equivalenti referral.
    """
    
    # Flag globale per abilitare/disabilitare tutto il sistema di referral
    REFERRAL_SYSTEM_ENABLED = True
    
    # Percorso del file JSON che contiene il database dei referral
    DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'referral_links.json')
    
    # Dizionario che mappa gli URL originali ai loro equivalenti referral
    _referral_db = {}
    
    # Dizionario che mappa i domini ai loro nomi di store
    DOMAIN_TO_STORE = {
        'thomann.de': 'Thomann',
        'andertons.co.uk': 'Andertons',
        'gear4music.com': 'Gear4music',
        'musik-produktiv.com': 'Musik Produktiv',
        'strumentimusicali.net': 'Strumenti Musicali',
        'centrochitarre.com': 'Centro Chitarre',
        'thomassone.fr': 'Tomassone'
    }
    
    # Configurazione per store attivi
    STORE_CONFIG = {
        'Thomann': True,
        'Andertons': False,
        'Gear4music': False,
        'Musik Produktiv': False,
        'Strumenti Musicali': False,
        'Centro Chitarre': False,
        'Tomassone': False
    }
    
    @classmethod
    def initialize(cls):
        """
        Inizializza il database dei referral caricandolo dal file JSON.
        Se il file non esiste, crea un database vuoto.
        """
        # Crea la directory data se non esiste
        os.makedirs(os.path.dirname(cls.DB_FILE), exist_ok=True)
        
        # Carica il database dal file JSON se esiste
        if os.path.exists(cls.DB_FILE):
            try:
                with open(cls.DB_FILE, 'r', encoding='utf-8') as f:
                    cls._referral_db = json.load(f)
                logger.info(f"Database referral caricato: {len(cls._referral_db)} link trovati")
            except Exception as e:
                logger.error(f"Errore durante il caricamento del database referral: {str(e)}")
                cls._referral_db = {}
        else:
            logger.info("Database referral non trovato, creazione di un nuovo database vuoto")
            cls._referral_db = {}
            cls._save_db()
    
    @classmethod
    def _save_db(cls):
        """
        Salva il database dei referral nel file JSON.
        """
        try:
            with open(cls.DB_FILE, 'w', encoding='utf-8') as f:
                json.dump(cls._referral_db, f, indent=2, ensure_ascii=False)
            logger.info(f"Database referral salvato: {len(cls._referral_db)} link")
        except Exception as e:
            logger.error(f"Errore durante il salvataggio del database referral: {str(e)}")
    
    @classmethod
    def add_referral_link(cls, original_url, referral_url, store_name=None):
        """
        Aggiunge un link referral al database.
        
        Args:
            original_url (str): L'URL originale del prodotto
            referral_url (str): L'URL con referral
            store_name (str, optional): Il nome dello store (es. "Thomann")
        
        Returns:
            bool: True se l'operazione è riuscita, False altrimenti
        """
        if not original_url or not referral_url:
            logger.warning("URL originale o referral mancante")
            return False
        
        # Normalizza gli URL (rimuovi trailing slash, ecc.)
        original_url = cls._normalize_url(original_url)
        referral_url = cls._normalize_url(referral_url)
        
        # Se non è specificato lo store, prova a determinarlo dall'URL
        if not store_name:
            store_name = cls._get_store_from_url(original_url)
        
        # Verifica se lo store è abilitato
        if store_name and not cls.STORE_CONFIG.get(store_name, False):
            logger.info(f"Referral non aggiunto: store {store_name} disabilitato")
            return False
        
        # Aggiungi il link al database
        cls._referral_db[original_url] = {
            'referral_url': referral_url,
            'store': store_name,
            'added_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Salva il database
        cls._save_db()
        
        logger.info(f"Referral aggiunto per {store_name}: {original_url} -> {referral_url}")
        return True
    
    @classmethod
    def get_referral_link(cls, url):
        """
        Ottiene il link referral per un URL originale.
        
        Args:
            url (str): L'URL originale del prodotto
            
        Returns:
            str: L'URL con referral se disponibile, altrimenti l'URL originale
        """
        if not cls.REFERRAL_SYSTEM_ENABLED:
            return url
        
        if not url or url == "N/A":
            return url
        
        # Normalizza l'URL
        normalized_url = cls._normalize_url(url)
        
        # Verifica se l'URL è nel database
        if normalized_url in cls._referral_db:
            referral_data = cls._referral_db[normalized_url]
            store_name = referral_data.get('store', 'Sconosciuto')
            
            # Verifica se lo store è abilitato
            if store_name and not cls.STORE_CONFIG.get(store_name, True):
                return url
            
            referral_url = referral_data.get('referral_url')
            if referral_url:
                logger.info(f"✅ Referral trovato per {store_name}: {url} -> {referral_url}")
                return referral_url
        
        # Se non è stato trovato un match esatto, prova con il pattern matching
        store_name = cls._get_store_from_url(url)
        if store_name and cls.STORE_CONFIG.get(store_name, False):
            logger.debug(f"Nessun referral esatto trovato per {url} ({store_name})")
        
        return url
    
    @classmethod
    def _normalize_url(cls, url):
        """
        Normalizza un URL per il confronto.
        
        Args:
            url (str): L'URL da normalizzare
            
        Returns:
            str: L'URL normalizzato
        """
        if not url:
            return url
        
        # Rimuovi trailing slash
        if url.endswith('/'):
            url = url[:-1]
        
        # Altre normalizzazioni possono essere aggiunte qui
        
        return url
    
    @classmethod
    def _get_store_from_url(cls, url):
        """
        Determina lo store da un URL.
        
        Args:
            url (str): L'URL da analizzare
            
        Returns:
            str: Il nome dello store, o None se non determinabile
        """
        if not url:
            return None
        
        try:
            domain = urlparse(url).netloc
            # Rimuovi www. se presente
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Cerca una corrispondenza nel dizionario dei domini
            for known_domain, store_name in cls.DOMAIN_TO_STORE.items():
                if known_domain in domain:
                    return store_name
        except:
            pass
        
        return None
    
    @classmethod
    def bulk_import_referrals(cls, referrals_data):
        """
        Importa in blocco una lista di referral.
        
        Args:
            referrals_data (list): Lista di dizionari con chiavi 'original_url', 'referral_url' e opzionalmente 'store'
            
        Returns:
            int: Numero di referral importati con successo
        """
        if not referrals_data:
            return 0
        
        count = 0
        for item in referrals_data:
            original_url = item.get('original_url')
            referral_url = item.get('referral_url')
            store_name = item.get('store')
            
            if original_url and referral_url:
                if cls.add_referral_link(original_url, referral_url, store_name):
                    count += 1
        
        logger.info(f"Importazione in blocco completata: {count}/{len(referrals_data)} referral importati")
        return count
    
    @classmethod
    def log_referral_status(cls):
        """
        Registra lo stato del sistema di referral all'avvio dell'applicazione.
        """
        if not cls.REFERRAL_SYSTEM_ENABLED:
            logger.info("🔴 Sistema di referral DB DISABILITATO globalmente")
            return
        
        logger.info("🟢 Sistema di referral DB ATTIVO")
        logger.info(f"Database: {cls.DB_FILE}")
        logger.info(f"Numero di referral nel database: {len(cls._referral_db)}")
        
        logger.info("Status dei referral per negozio:")
        for store_name, enabled in cls.STORE_CONFIG.items():
            status = "✅ ATTIVO" if enabled else "❌ DISABILITATO"
            logger.info(f"  - {store_name}: {status}")
        
        # Conta i referral per ogni store
        store_counts = {}
        for url, data in cls._referral_db.items():
            store = data.get('store', 'Sconosciuto')
            store_counts[store] = store_counts.get(store, 0) + 1
        
        if store_counts:
            logger.info("Distribuzione dei referral:")
            for store, count in store_counts.items():
                logger.info(f"  - {store}: {count} referral")


# Inizializza il database all'importazione del modulo
ReferralDBManager.initialize()


# Esempio di utilizzo:
if __name__ == "__main__":
    # Abilita solo Thomann per i test
    ReferralDBManager.STORE_CONFIG['Thomann'] = True
    
    # Aggiungi alcuni link di esempio
    ReferralDBManager.add_referral_link(
        "https://www.thomann.de/it/fender_stratocaster.htm",
        "https://www.thomann.de/it/fender_stratocaster.htm?partner_id=INSTRINDER123",
        "Thomann"
    )
    
    # Test di ricerca
    original_url = "https://www.thomann.de/it/fender_stratocaster.htm"
    referral_url = ReferralDBManager.get_referral_link(original_url)
    
    print(f"\nTest ricerca referral:")
    print(f"Original: {original_url}")
    print(f"Referral: {referral_url}")
    
    # Mostra lo stato del sistema
    ReferralDBManager.log_referral_status()
