"""
Modulo per la risoluzione automatica dei CAPTCHA utilizzando il servizio 2Captcha.
"""
import os
import time
import base64
import requests
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configura il logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Chiave API per 2Captcha - Sostituisci con la tua chiave
API_KEY = "INSERISCI_QUI_LA_TUA_CHIAVE_API"

def solve_image_captcha(driver, captcha_selector='img.captcha', input_selector='input[name="captcha"]', submit_selector='button[type="submit"], input[type="submit"]'):
    """
    Risolve un CAPTCHA basato su immagine utilizzando 2Captcha.
    
    Args:
        driver: Istanza del webdriver Selenium
        captcha_selector: Selettore CSS dell'immagine del CAPTCHA
        input_selector: Selettore CSS del campo di input per la soluzione
        submit_selector: Selettore CSS del pulsante di invio
        
    Returns:
        bool: True se il CAPTCHA è stato risolto con successo, False altrimenti
    """
    if not API_KEY or API_KEY == "INSERISCI_QUI_LA_TUA_CHIAVE_API":
        logger.error("❌ Chiave API 2Captcha non configurata")
        return False
    
    try:
        # Trova l'elemento del CAPTCHA
        captcha_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, captcha_selector))
        )
        
        # Ottieni l'URL dell'immagine o fai uno screenshot
        captcha_url = captcha_element.get_attribute('src')
        
        if not captcha_url or captcha_url.startswith('data:'):
            # Se l'immagine è incorporata o non ha un URL, fai uno screenshot
            logger.info("📸 Acquisizione screenshot del CAPTCHA...")
            captcha_element.screenshot('temp_captcha.png')
            
            # Leggi l'immagine come base64
            with open('temp_captcha.png', 'rb') as f:
                captcha_base64 = base64.b64encode(f.read()).decode('utf-8')
            
            # Elimina il file temporaneo
            os.remove('temp_captcha.png')
        else:
            # Scarica l'immagine dall'URL
            logger.info(f"🌐 Download immagine CAPTCHA da {captcha_url}...")
            response = requests.get(captcha_url)
            captcha_base64 = base64.b64encode(response.content).decode('utf-8')
        
        # Invia l'immagine a 2Captcha
        logger.info("🔄 Invio CAPTCHA a 2Captcha per la risoluzione...")
        response = requests.post('https://2captcha.com/in.php', data={
            'key': API_KEY,
            'method': 'base64',
            'body': captcha_base64,
            'json': 1
        })
        
        if response.status_code != 200:
            logger.error(f"❌ Errore nella richiesta a 2Captcha: {response.status_code}")
            return False
        
        result = response.json()
        if result['status'] != 1:
            logger.error(f"❌ Errore da 2Captcha: {result['request']}")
            return False
        
        # Ottieni l'ID della richiesta
        request_id = result['request']
        logger.info(f"✅ CAPTCHA inviato con successo, ID: {request_id}")
        
        # Attendi la soluzione (polling)
        for _ in range(30):  # Attendi fino a 30 * 5 = 150 secondi
            time.sleep(5)
            logger.info("⏳ Attesa della soluzione...")
            
            response = requests.get(f'https://2captcha.com/res.php?key={API_KEY}&action=get&id={request_id}&json=1')
            result = response.json()
            
            if result['status'] == 1:
                # Abbiamo la soluzione!
                captcha_solution = result['request']
                logger.info(f"✅ CAPTCHA risolto: {captcha_solution}")
                
                # Inserisci la soluzione nel campo di input
                input_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, input_selector))
                )
                input_element.clear()
                input_element.send_keys(captcha_solution)
                
                # Invia il form
                submit_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, submit_selector))
                )
                submit_button.click()
                
                # Attendi che la pagina si carichi
                time.sleep(3)
                
                # Verifica se il CAPTCHA è stato risolto correttamente
                if any(text in driver.page_source.lower() for text in ['captcha', 'verifica', 'security check', 'accesso bloccato']):
                    logger.warning("⚠️ Il CAPTCHA non è stato risolto correttamente")
                    return False
                else:
                    logger.info("🎉 CAPTCHA risolto con successo!")
                    return True
            
            elif result['request'] == 'CAPCHA_NOT_READY':
                continue
            else:
                logger.error(f"❌ Errore nella risoluzione del CAPTCHA: {result['request']}")
                return False
        
        logger.error("❌ Timeout nella risoluzione del CAPTCHA")
        return False
    
    except Exception as e:
        logger.error(f"❌ Errore durante la risoluzione del CAPTCHA: {str(e)}")
        return False

def solve_recaptcha(driver, site_key=None, site_key_selector='[data-sitekey]', submit_selector='button[type="submit"], input[type="submit"]'):
    """
    Risolve un reCAPTCHA utilizzando 2Captcha.
    
    Args:
        driver: Istanza del webdriver Selenium
        site_key: Chiave del sito per reCAPTCHA (opzionale, verrà estratta se non fornita)
        site_key_selector: Selettore CSS dell'elemento che contiene la chiave del sito
        submit_selector: Selettore CSS del pulsante di invio
        
    Returns:
        bool: True se il reCAPTCHA è stato risolto con successo, False altrimenti
    """
    if not API_KEY or API_KEY == "INSERISCI_QUI_LA_TUA_CHIAVE_API":
        logger.error("❌ Chiave API 2Captcha non configurata")
        return False
    
    try:
        # Ottieni l'URL della pagina
        page_url = driver.current_url
        
        # Se la site_key non è fornita, cerca di estrarla dalla pagina
        if not site_key:
            try:
                site_key_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, site_key_selector))
                )
                site_key = site_key_element.get_attribute('data-sitekey')
            except:
                # Cerca la chiave nel codice sorgente della pagina
                page_source = driver.page_source
                import re
                site_key_match = re.search(r'data-sitekey="([^"]+)"', page_source)
                if site_key_match:
                    site_key = site_key_match.group(1)
                else:
                    logger.error("❌ Impossibile trovare la chiave del sito reCAPTCHA")
                    return False
        
        logger.info(f"🔑 Chiave del sito reCAPTCHA trovata: {site_key}")
        
        # Invia la richiesta a 2Captcha
        logger.info("🔄 Invio reCAPTCHA a 2Captcha per la risoluzione...")
        response = requests.post('https://2captcha.com/in.php', data={
            'key': API_KEY,
            'method': 'userrecaptcha',
            'googlekey': site_key,
            'pageurl': page_url,
            'json': 1
        })
        
        if response.status_code != 200:
            logger.error(f"❌ Errore nella richiesta a 2Captcha: {response.status_code}")
            return False
        
        result = response.json()
        if result['status'] != 1:
            logger.error(f"❌ Errore da 2Captcha: {result['request']}")
            return False
        
        # Ottieni l'ID della richiesta
        request_id = result['request']
        logger.info(f"✅ reCAPTCHA inviato con successo, ID: {request_id}")
        
        # Attendi la soluzione (polling)
        for _ in range(30):  # Attendi fino a 30 * 5 = 150 secondi
            time.sleep(5)
            logger.info("⏳ Attesa della soluzione...")
            
            response = requests.get(f'https://2captcha.com/res.php?key={API_KEY}&action=get&id={request_id}&json=1')
            result = response.json()
            
            if result['status'] == 1:
                # Abbiamo la soluzione!
                g_response = result['request']
                logger.info("✅ reCAPTCHA risolto!")
                
                # Inserisci la soluzione tramite JavaScript
                driver.execute_script(f'document.getElementById("g-recaptcha-response").innerHTML="{g_response}";')
                
                # Esegui il callback di reCAPTCHA se presente
                driver.execute_script('if (typeof ___grecaptcha_cfg !== "undefined") { '
                                     'Object.keys(___grecaptcha_cfg.clients).forEach(function(key) { '
                                     'const client = ___grecaptcha_cfg.clients[key]; '
                                     'Object.keys(client).forEach(function(idx) { '
                                     'if (typeof client[idx].callback === "function") { client[idx].callback("' + g_response + '"); } }); }); }')
                
                # Invia il form
                try:
                    submit_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, submit_selector))
                    )
                    submit_button.click()
                except:
                    logger.warning("⚠️ Impossibile trovare il pulsante di invio, prova a continuare...")
                
                # Attendi che la pagina si carichi
                time.sleep(3)
                
                # Verifica se il CAPTCHA è stato risolto correttamente
                if any(text in driver.page_source.lower() for text in ['captcha', 'verifica', 'security check', 'accesso bloccato']):
                    logger.warning("⚠️ Il reCAPTCHA non è stato risolto correttamente")
                    return False
                else:
                    logger.info("🎉 reCAPTCHA risolto con successo!")
                    return True
            
            elif result['request'] == 'CAPCHA_NOT_READY':
                continue
            else:
                logger.error(f"❌ Errore nella risoluzione del reCAPTCHA: {result['request']}")
                return False
        
        logger.error("❌ Timeout nella risoluzione del reCAPTCHA")
        return False
    
    except Exception as e:
        logger.error(f"❌ Errore durante la risoluzione del reCAPTCHA: {str(e)}")
        return False

def detect_and_solve_captcha(driver):
    """
    Rileva e risolve automaticamente diversi tipi di CAPTCHA.
    
    Args:
        driver: Istanza del webdriver Selenium
        
    Returns:
        bool: True se il CAPTCHA è stato risolto con successo, False altrimenti
    """
    page_source = driver.page_source.lower()
    
    # Verifica la presenza di reCAPTCHA
    if 'recaptcha' in page_source or 'g-recaptcha' in page_source:
        logger.info("🔍 Rilevato reCAPTCHA")
        return solve_recaptcha(driver)
    
    # Verifica la presenza di CAPTCHA basato su immagine
    captcha_selectors = [
        'img.captcha', 
        'img[alt*="captcha"]', 
        'img[src*="captcha"]',
        'img[id*="captcha"]',
        'img[class*="captcha"]'
    ]
    
    for selector in captcha_selectors:
        try:
            if driver.find_element(By.CSS_SELECTOR, selector):
                logger.info(f"🔍 Rilevato CAPTCHA basato su immagine con selettore: {selector}")
                return solve_image_captcha(driver, captcha_selector=selector)
        except:
            continue
    
    logger.warning("⚠️ Nessun CAPTCHA riconosciuto")
    return False

if __name__ == "__main__":
    # Test del risolutore di CAPTCHA
    from selenium import webdriver
    import undetected_chromedriver as uc
    
    # Configura il driver
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = uc.Chrome(options=options)
    
    try:
        # Vai a un sito con CAPTCHA per testare
        driver.get("https://www.strumentimusicali.net/advanced_search_result.php?inc_subcat=1&keywords=eventide+h90")
        
        # Attendi che la pagina si carichi
        time.sleep(3)
        
        # Verifica se c'è un CAPTCHA e prova a risolverlo
        if any(text in driver.page_source.lower() for text in ['captcha', 'verifica', 'security check', 'accesso bloccato']):
            logger.info("🔍 CAPTCHA rilevato, tentativo di risoluzione...")
            if detect_and_solve_captcha(driver):
                logger.info("🎉 CAPTCHA risolto con successo!")
                
                # Salva i cookie per uso futuro
                import json
                cookies = driver.get_cookies()
                with open('strumentimusicali_cookies.json', 'w') as f:
                    json.dump(cookies, f)
                logger.info(f"🍪 Salvati {len(cookies)} cookies in strumentimusicali_cookies.json")
            else:
                logger.error("❌ Impossibile risolvere il CAPTCHA")
        else:
            logger.info("✅ Nessun CAPTCHA rilevato")
    
    finally:
        # Chiudi il browser
        driver.quit()
