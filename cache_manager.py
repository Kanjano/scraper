#!/usr/bin/env python3
"""
Gestore della cache per undetected_chromedriver.
Fornisce funzioni per pulire la cache in modo intelligente.
"""

import os
import time
import shutil
import logging
import random
from datetime import datetime, timedelta

# Configura il logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Percorso della cache di undetected_chromedriver
CACHE_DIR = os.path.expanduser('~/Library/Application Support/undetected_chromedriver')

# File per tenere traccia dell'ultima pulizia
LAST_CLEANUP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.last_cache_cleanup')

def get_cache_size():
    """Restituisce la dimensione della cache in MB."""
    if not os.path.exists(CACHE_DIR):
        return 0
    
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(CACHE_DIR):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    
    return total_size / (1024 * 1024)  # Converti in MB

def get_last_cleanup_time():
    """Restituisce il timestamp dell'ultima pulizia della cache."""
    if not os.path.exists(LAST_CLEANUP_FILE):
        return 0
    
    try:
        with open(LAST_CLEANUP_FILE, 'r') as f:
            return float(f.read().strip())
    except (ValueError, IOError):
        return 0

def set_last_cleanup_time():
    """Imposta il timestamp dell'ultima pulizia della cache."""
    try:
        with open(LAST_CLEANUP_FILE, 'w') as f:
            f.write(str(time.time()))
    except IOError as e:
        logger.error(f"Errore durante la scrittura del timestamp di pulizia: {e}")

def should_cleanup_cache():
    """
    Determina se è necessario pulire la cache in base a:
    1. Tempo trascorso dall'ultima pulizia
    2. Dimensione della cache
    3. Probabilità casuale (per evitare pulizie simultanee in ambienti multi-utente)
    """
    # Se la cache non esiste, non è necessario pulirla
    if not os.path.exists(CACHE_DIR):
        return False
    
    # Ottieni il timestamp dell'ultima pulizia
    last_cleanup = get_last_cleanup_time()
    now = time.time()
    
    # Se l'ultima pulizia è avvenuta più di 24 ore fa, pulisci la cache
    if now - last_cleanup > 86400:  # 24 ore in secondi
        logger.info("È passato più di un giorno dall'ultima pulizia della cache")
        return True
    
    # Se la cache è più grande di 100 MB, puliscila
    cache_size = get_cache_size()
    if cache_size > 100:
        logger.info(f"La cache è troppo grande ({cache_size:.2f} MB)")
        return True
    
    # Probabilità casuale del 5% di pulire la cache
    if random.random() < 0.05:
        logger.info("Pulizia casuale della cache")
        return True
    
    return False

def cleanup_cache(force=False):
    """
    Pulisce la cache di undetected_chromedriver.
    
    Args:
        force (bool): Se True, forza la pulizia indipendentemente dalle condizioni
    
    Returns:
        bool: True se la pulizia è avvenuta con successo, False altrimenti
    """
    if not force and not should_cleanup_cache():
        logger.debug("Non è necessario pulire la cache")
        return False
    
    if not os.path.exists(CACHE_DIR):
        logger.info("La cache non esiste, nessuna pulizia necessaria")
        return True
    
    try:
        logger.info(f"Pulizia della cache in {CACHE_DIR}")
        shutil.rmtree(CACHE_DIR)
        logger.info("Cache pulita con successo")
        set_last_cleanup_time()
        return True
    except Exception as e:
        logger.error(f"Errore durante la pulizia della cache: {e}")
        return False

def cleanup_on_error(error_message):
    """
    Pulisce la cache se l'errore è correlato al driver.
    
    Args:
        error_message (str): Messaggio di errore da analizzare
        
    Returns:
        bool: True se la cache è stata pulita, False altrimenti
    """
    # Lista di pattern di errore che indicano problemi con il driver
    driver_error_patterns = [
        "No such file or directory",
        "Cannot connect to the Service",
        "Can not connect to the Service",
        "chromedriver",
        "Chrome version",
        "session not created",
        "version mismatch",
        "browser failed to start",
        "timeout",
        "unable to discover open pages"
    ]
    
    # Se l'errore contiene uno dei pattern, pulisci la cache
    if any(pattern.lower() in error_message.lower() for pattern in driver_error_patterns):
        logger.info(f"Errore correlato al driver rilevato: {error_message}")
        return cleanup_cache(force=True)
    
    return False

if __name__ == "__main__":
    # Se eseguito direttamente, pulisci la cache
    if cleanup_cache(force=True):
        print("✅ Cache pulita con successo")
    else:
        print("❌ Errore durante la pulizia della cache")
