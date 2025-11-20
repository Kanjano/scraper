import re
import os
import json
import time
import random
from urllib.parse import urljoin, quote_plus

# Importa il risolutore di CAPTCHA
from captcha_solver import detect_and_solve_captcha
from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fake_useragent import UserAgent
import logging
from browser_manager import BrowserManager

# Configura il logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configura un user agent casuale
ua = UserAgent()


def make_request(url, max_retries=3, timeout=30):
    """Esegue una richiesta HTTP con Selenium per aggirare i controlli anti-bot."""
    driver = None
    
    for attempt in range(max_retries):
        try:
            driver = BrowserManager.create_driver()
            if not driver:
                logger.error("Impossibile creare il driver")
                return []
            
            # Vai alla pagina di ricerca
            logger.info(f"🌍 Accesso alla pagina: {url}")
            try:
                driver.get(url)
                logger.info("✅ Pagina caricata con successo")
                
                # Controlla se siamo stati reindirizzati a una pagina di sicurezza o di verifica
                if "captcha" in driver.page_source.lower() or "verifica" in driver.page_source.lower():
                    logger.warning("⚠️ Rilevata pagina di verifica o CAPTCHA")
                    
                # Salva la pagina HTML per debug
                with open('debug_strumenti_last_page.html', 'w', encoding='utf-8') as f:
                    f.write(driver.page_source)
                logger.info("💾 Pagina HTML salvata in 'debug_strumenti_last_page.html'")
                
                # Fai uno screenshot per debug
                try:
                    driver.save_screenshot('debug_strumenti_screenshot.png')
                    logger.info("📸 Screenshot salvato in 'debug_strumenti_screenshot.png'")
                except Exception as e:
                    logger.warning(f"⚠️ Impossibile salvare lo screenshot: {str(e)}")
                    
            except Exception as e:
                logger.error(f"❌ Errore durante il caricamento della pagina: {str(e)}")
                BrowserManager.close_driver(driver)
                return []
            
            # Aggiungi un ritardo casuale tra le richieste
            time.sleep(random.uniform(2.0, 5.0))
            
            # Imposta il timeout per il caricamento della pagina
            driver.set_page_load_timeout(timeout)
            
            # Attendi che la pagina sia completamente caricata
            try:
                logger.info("⏳ Attesa del caricamento della pagina...")
                WebDriverWait(driver, 20).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
                logger.info("✅ Pagina completamente caricata")
            except TimeoutException:
                logger.warning("⚠️ Timeout durante l'attesa del caricamento della pagina")
                # Prova comunque a procedere con il contenuto caricato
            except Exception as e:
                logger.error(f"❌ Errore durante l'attesa del caricamento: {str(e)}")
                BrowserManager.close_driver(driver)
                return []
            
            # Scrolla la pagina per caricare i contenuti dinamici
            logger.info("🔄 Scrolling della pagina per caricare i contenuti...")
            try:
                last_height = driver.execute_script("return document.body.scrollHeight")
                scroll_attempts = 0
                max_scroll_attempts = 5
                
                for i in range(max_scroll_attempts):
                    logger.info(f"   ↳ Scroll {i+1}/{max_scroll_attempts}")
                    # Scrolla fino in fondo
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1.5)  # Attendi il caricamento
                    
                    # Controlla se ci sono nuovi contenuti
                    new_height = driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        scroll_attempts += 1
                        if scroll_attempts >= 2:  # Se non ci sono cambiamenti per 2 volte di fila, esci
                            break
                    else:
                        scroll_attempts = 0  # Reset del contatore se ci sono nuovi contenuti
                        
                    last_height = new_height
                    
                    # Scrolla anche verso l'alto ogni tanto per attivare eventuali lazy loading
                    if i % 2 == 0:
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
                        time.sleep(0.5)
                        
                logger.info("✅ Scrolling completato")
                
            except Exception as e:
                logger.error(f"❌ Errore durante lo scrolling della pagina: {str(e)}")
                # Prova comunque a procedere con il contenuto caricato
            
            # Ritorna il codice HTML della pagina
            return driver.page_source
            
        except TimeoutException:
            logger.warning(f"Timeout durante il caricamento della pagina (tentativo {attempt + 1}/{max_retries})")
            if attempt == max_retries - 1:
                logger.error("Timeout massimo raggiunto")
                return None
                
        except WebDriverException as e:
            logger.warning(f"Errore WebDriver (tentativo {attempt + 1}/{max_retries}): {str(e)[:200]}")
            if attempt == max_retries - 1:
                logger.error("Errore WebDriver non risolvibile")
                return None
                
        except Exception as e:
            logger.error(f"Errore imprevisto (tentativo {attempt + 1}/{max_retries}): {str(e)}")
            if attempt == max_retries - 1:
                return None
                
        finally:
            # Aggiungi un ritardo tra i tentativi
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 3
                logger.info(f"Attesa di {wait_time} secondi prima di riprovare...")
                time.sleep(wait_time)
    
    # Chiudi il driver se è stato creato
    BrowserManager.close_driver(driver)
            
    return None

def extract_product_details(driver, url):
    """Estrae i dettagli di un prodotto dalla sua pagina utilizzando Selenium."""
    logger.info(f"🔍 Estrazione dettagli da: {url}")
    
    try:
        # Vai alla pagina del prodotto
        driver.get(url)
        
        # Attendi che la pagina sia completamente caricata
        try:
            logger.info("⏳ Attesa del caricamento della pagina...")
            WebDriverWait(driver, 20).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            logger.info("✅ Pagina completamente caricata")
        except TimeoutException:
            logger.warning("⚠️ Timeout durante l'attesa del caricamento della pagina")
            # Prova comunque a procedere con il contenuto caricato
        except Exception as e:
            logger.error(f"❌ Errore durante l'attesa del caricamento: {str(e)}")
            if driver:
                # Non chiudiamo il driver qui perché è passato dall'esterno
                pass
            return None, None
        
        # Scrolla la pagina per caricare i contenuti dinamici
        logger.info("🔄 Scrolling della pagina per caricare i contenuti...")
        try:
            last_height = driver.execute_script("return document.body.scrollHeight")
            scroll_attempts = 0
            max_scroll_attempts = 5
            
            for i in range(max_scroll_attempts):
                logger.info(f"   ↳ Scroll {i+1}/{max_scroll_attempts}")
                # Scrolla fino in fondo
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1.5)  # Attendi il caricamento
                
                # Controlla se ci sono nuovi contenuti
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    scroll_attempts += 1
                    if scroll_attempts >= 2:  # Se non ci sono cambiamenti per 2 volte di fila, esci
                        break
                else:
                    scroll_attempts = 0  # Reset del contatore se ci sono nuovi contenuti
                    
                last_height = new_height
                
                # Scrolla anche verso l'alto ogni tanto per attivare eventuali lazy loading
                if i % 2 == 0:
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
                    time.sleep(0.5)
                    
            logger.info("✅ Scrolling completato")
            
        except Exception as e:
            logger.error(f"❌ Errore durante lo scrolling della pagina: {str(e)}")
            # Prova comunque a procedere con il contenuto caricato
        
        # Analizza la pagina con BeautifulSoup
        logger.info("🔍 Analisi della pagina con BeautifulSoup...")
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        # Selettori per l'immagine del prodotto
        img_selectors = [
            'img.gallery-placeholder__image',
            'img#image-main',
            'div.product.media img',
            'div.gallery-placeholder img',
            'img[itemprop="image"]',
            'img.product-image-photo',
            'div.product-img-box img',
            'div.product.media img.fotorama__img',
            'div.product.media img.fotorama__img--img'
        ]
        
        # Cerca l'immagine principale
        img_url = None
        for selector in img_selectors:
            try:
                img_elem = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                img_url = img_elem.get_attribute('src') or img_elem.get_attribute('data-src')
                if img_url:
                    if not img_url.startswith(('http', '//')):
                        img_url = urljoin('https://www.strumentimusicali.net', img_url)
                    break
            except (TimeoutException, NoSuchElementException):
                continue
        
        # Se non trovata con Selenium, prova con BeautifulSoup
        if not img_url:
            for selector in img_selectors:
                img_elem = soup.select_one(selector)
                if img_elem:
                    img_url = img_elem.get('src') or img_elem.get('data-src')
                    if img_url:
                        if not img_url.startswith(('http', '//')):
                            img_url = urljoin('https://www.strumentimusicali.net', img_url)
                        break
        
        # Selezionatori per la descrizione
        desc_selectors = [
            'div.product.attribute.description',
            'div.description',
            'div.product.info.detailed',
            'div#description',
            'div.product-description',
            'div.std',
            'div[itemprop="description"]',
            'div.product.info.detailed div[data-role="content"]',
            'div#product-description-details',
            'div.product.info.detailed div.value'
        ]
        
        # Estrai la descrizione
        description = ""
        for selector in desc_selectors:
            try:
                desc_elem = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                description = driver.execute_script("return arguments[0].innerText;", desc_elem)
                if description and len(description) > 10:  # Verifica che la descrizione abbia contenuto
                    description = ' '.join(description.split())[:300] + '...'  # Limita la lunghezza
                    break
            except (TimeoutException, NoSuchElementException):
                continue
        
        # Se non trovata con Selenium, prova con BeautifulSoup
        if not description:
            for selector in desc_selectors:
                desc_elem = soup.select_one(selector)
                if desc_elem:
                    description = desc_elem.get_text(strip=True)
                    if description and len(description) > 10:
                        description = ' '.join(description.split())[:300] + '...'
                        break
        
        logger.info(f"✅ Estrazione completata per: {url}")
        return img_url, description
        
    except Exception as e:
        logger.error(f"❌ Errore durante l'estrazione dei dettagli: {str(e)}")
        return None, None

def clean_price(price_text):
    """Pulisce e converte il testo del prezzo in un numero float.
    Gestisce sia il formato italiano (3.399,00 €) che il formato anglosassone (1,599.00 €).
    """
    if not price_text:
        return 0.0
    
    try:
        # Rimuovi tutto tranne numeri, virgole e punti
        price = re.sub(r'[^\d,.]', '', price_text)
        
        # Determina il formato del prezzo
        if ',' in price and '.' in price:
            # Formato misto, determina quale è il separatore decimale
            # In genere, il separatore decimale è l'ultimo
            if price.rindex(',') > price.rindex('.'):
                # Formato italiano con virgola come separatore decimale (3.399,00)
                price = price.replace('.', '')  # Rimuovi i punti (separatori delle migliaia)
                price = price.replace(',', '.')  # Sostituisci la virgola con il punto
            else:
                # Formato anglosassone con punto come separatore decimale (1,599.00)
                price = price.replace(',', '')  # Rimuovi le virgole (separatori delle migliaia)
        elif ',' in price:
            # Solo virgole, assumiamo formato italiano
            price = price.replace(',', '.')
        elif '.' in price:
            # Solo punti, dobbiamo determinare se è un separatore decimale o delle migliaia
            # Se il punto è seguito da esattamente 2 cifre, è probabilmente un separatore decimale
            # Altrimenti, è probabilmente un separatore delle migliaia
            parts = price.split('.')
            if len(parts) == 2 and len(parts[1]) != 2:
                # Probabilmente un separatore delle migliaia (es. 1.599)
                price = price.replace('.', '')
        
        return float(price)
    except (ValueError, TypeError) as e:
        logger.error(f"⚠️ Impossibile convertire il prezzo: {price_text} - Errore: {str(e)}")
        return 0.0

def search_strumentimusicali(prodotto, max_results=10):
    """
    Cerca prodotti su StrumentiMusicali.net
    
    Args:
        prodotto (str): Il prodotto da cercare
        max_results (int): Numero massimo di risultati da restituire
        
    Returns:
        list: Lista di dizionari contenenti i dettagli dei prodotti trovati
    """
    logger.info("\n" + "="*50)
    logger.info(f"🔄 AVVIO RICERCA PER: '{prodotto}'")
    logger.info("="*50)
    
    if not prodotto or not isinstance(prodotto, str):
        logger.error("❌ ERRORE: Nessun termine di ricerca fornito")
        return []

    # Prepara la query e le parole chiave
    base_url = "https://www.strumentimusicali.net"
    search_url = f"{base_url}/advanced_search_result.php?inc_subcat=1&keywords={quote_plus(prodotto)}"
    
    # Estrai le parole chiave dalla query di ricerca
    parole_chiave = [p.lower() for p in prodotto.split() if len(p) > 2]
    
    if not parole_chiave:
        logger.error("❌ ERRORE: La ricerca deve contenere almeno una parola chiave valida (più di 2 caratteri)")
        return []
    
    logger.info(f"🔍 Query di ricerca: '{prodotto}'")
    logger.info(f"🌐 URL di ricerca: {search_url}")
    logger.info(f"🔑 Parole chiave: {parole_chiave}")
    logger.info(f"📊 Risultati massimi richiesti: {max_results}")
    
    # Utilizziamo undetected_chromedriver per evitare il rilevamento dell'automazione
    driver = None
    risultati = []
    
    try:
        logger.info("🚀 Inizializzazione del browser con BrowserManager...")
        
        driver = BrowserManager.create_driver()
        if not driver:
            logger.error("❌ Impossibile inizializzare il browser")
            return []
        
        # Esegui JavaScript per nascondere il fatto che il browser è controllato da WebDriver
        try:
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        except:
            pass
        
        logger.info("✅ Browser inizializzato con successo")
        logger.info(f"🌍 Accesso alla pagina: {search_url}")
        
        # Aggiungi un ritardo casuale prima di accedere alla pagina
        time.sleep(random.uniform(2, 4))
        driver.get(search_url)
        
        # Attendi che la pagina sia completamente caricata
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        logger.info("✅ Pagina caricata con successo")
        
        # Simula comportamento umano: scrolling lento e casuale
        logger.info("👤 Simulazione comportamento umano...")
        for _ in range(3):
            # Scroll casuale
            scroll_height = random.uniform(300, 700)
            driver.execute_script(f"window.scrollBy(0, {scroll_height});")
            time.sleep(random.uniform(1, 2.5))
        
        # Verifica se esistono cookie salvati da una sessione precedente
        cookie_file = 'strumentimusicali_cookies.json'
        cookies_loaded = False
        
        if os.path.exists(cookie_file):
            try:
                logger.info(f"🍪 Caricamento cookies da {cookie_file}...")
                with open(cookie_file, 'r') as f:
                    cookies = json.load(f)
                
                # Vai prima alla homepage per impostare il dominio corretto
                driver.get(base_url)
                time.sleep(2)
                
                # Aggiungi i cookie salvati
                for cookie in cookies:
                    try:
                        driver.add_cookie(cookie)
                    except Exception as e:
                        logger.warning(f"⚠️ Impossibile aggiungere cookie: {str(e)}")
                
                logger.info(f"✅ Caricati {len(cookies)} cookies")
                cookies_loaded = True
                
                # Ora vai all'URL di ricerca con i cookie caricati
                driver.get(search_url)
                time.sleep(2)
            except Exception as e:
                logger.error(f"❌ Errore nel caricamento dei cookies: {str(e)}")
        
        # Controlla se siamo stati reindirizzati a una pagina di sicurezza o di verifica
        page_source = driver.page_source.lower()
        if 'recaptcha' in page_source:
            logger.warning("⚠️ Rilevato reCAPTCHA invisibile")
            # Salva la pagina per debug
            with open('captcha_page.html', 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            logger.info("💾 Pagina con reCAPTCHA salvata in 'captcha_page.html'")
            
            # Estrai la chiave del sito reCAPTCHA
            import re
            site_key_match = re.search(r'recaptcha\/api\.js\?render=([\w\-_]+)', page_source)
            if site_key_match:
                site_key = site_key_match.group(1)
                logger.info(f"🔑 Chiave del sito reCAPTCHA trovata: {site_key}")
            
            # Tenta di bypassare il reCAPTCHA con JavaScript
            try:
                logger.info("🔍 Tentativo di bypassare il reCAPTCHA...")
                # Esegui JavaScript per simulare il completamento del reCAPTCHA
                driver.execute_script("""
                    // Simula il token di reCAPTCHA
                    var recaptchaCallback = function() {
                        console.log('reCAPTCHA callback simulato');
                    };
                    // Cerca tutti i callback di reCAPTCHA e chiamali
                    if (typeof ___grecaptcha_cfg !== 'undefined') {
                        Object.keys(___grecaptcha_cfg.clients).forEach(function(key) {
                            var client = ___grecaptcha_cfg.clients[key];
                            Object.keys(client).forEach(function(idx) {
                                if (typeof client[idx].callback === 'function') {
                                    client[idx].callback('simulated_token_' + Math.random().toString(36).substring(2));
                                }
                            });
                        });
                    }
                """)
                
                # Attendi un po' dopo l'esecuzione dello script
                time.sleep(2)
                
                logger.info("✅ Tentativo di bypass completato, procediamo con l'estrazione dei dati")
            except Exception as e:
                logger.warning(f"⚠️ Errore nel tentativo di bypass: {str(e)}")
            
            # Procediamo comunque con l'estrazione dei dati
            logger.info("🔍 Procediamo con l'estrazione dei dati nonostante il reCAPTCHA")
        
        elif any(text in page_source for text in ['captcha', 'verifica', 'security check', 'accesso bloccato']):
            logger.warning("⚠️ Rilevata altra forma di verifica o CAPTCHA")
            with open('captcha_page.html', 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            logger.info("💾 Pagina di verifica salvata in 'captcha_page.html'")
            
            # Procediamo comunque con l'estrazione dei dati
            logger.info("🔍 Procediamo con l'estrazione dei dati nonostante la verifica")
        
        # Salva i cookies per usi futuri
        cookies = driver.get_cookies()
        with open(cookie_file, 'w') as f:
            json.dump(cookies, f)
        logger.info(f"🍪 Salvati {len(cookies)} cookies in {cookie_file}")
        
        # Ottieni l'HTML aggiornato dopo lo scroll
        html = driver.page_source
        
        # Salva l'HTML per debug
        with open('strumentimusicali_results.html', 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info("💾 Pagina HTML salvata in 'strumentimusicali_results.html'")
        
        # Controlla se la pagina contiene risultati
        if "Nessun prodotto corrisponde ai criteri di ricerca" in html:
            logger.warning("⚠️ Nessun prodotto trovato per questa ricerca")
            return []
        
        # Analizza la pagina con BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        # Cerca i prodotti nella tabella di risultati
        logger.info("🔎 Ricerca dei prodotti nella pagina...")
        
        # Cerca la tabella principale dei prodotti
        product_table = soup.select_one('table.productListing')
        if not product_table:
            logger.warning("⚠️ Tabella dei prodotti non trovata")
            # Cerca altri elementi che potrebbero contenere prodotti
            product_items = []
            selectors = [
                'tr.productListing-odd', 'tr.productListing-even',
                'div.product-item', 'div.product-listing-item',
                'div.search-result-item'
            ]
            
            for selector in selectors:
                items = soup.select(selector)
                if items:
                    product_items.extend(items)
                    logger.info(f"✅ Trovati {len(items)} elementi con il selettore: {selector}")
        else:
            # Estrai le righe della tabella dei prodotti
            product_items = product_table.select('tr.productListing-odd, tr.productListing-even')
            logger.info(f"✅ Trovati {len(product_items)} prodotti nella tabella")
            
            # Se non ci sono righe specifiche, prendi tutte le righe tranne l'intestazione
            if not product_items:
                product_items = product_table.select('tr:not(.productListing-headerRow)')
                # Rimuovi l'intestazione se presente
                if product_items and 'productListing-headerRow' in product_items[0].get('class', []):
                    product_items = product_items[1:]
                logger.info(f"✅ Trovati {len(product_items)} prodotti nelle righe della tabella")
        
        # Verifica se abbiamo trovato prodotti
        if not product_items:
            logger.warning("⚠️ Nessun prodotto trovato nella pagina")
            # Prova a cercare qualsiasi elemento che contenga un prezzo e un link
            try:
                potential_products = soup.find_all(lambda tag: tag.find('a') and 
                                                (tag.find(string=re.compile(r'\d+[,\.]\d{2}\s*€')) or 
                                                tag.find(string=re.compile(r'€\s*\d+[,\.]\d{2}'))))
                
                if potential_products:
                    product_items = potential_products
                    logger.info(f"✅ Trovati {len(product_items)} potenziali prodotti con ricerca aggressiva")
            except Exception as e:
                logger.error(f"❌ Errore nella ricerca aggressiva: {str(e)}")
                
        # Verifica se abbiamo trovato prodotti
        if not product_items:
            logger.warning("⚠️ Nessun prodotto trovato con nessun metodo")
            return []
        
        if not product_items:
            logger.error("❌ Impossibile trovare prodotti nella pagina")
            with open('debug_strumentimusicali.html', 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            logger.info("💾 Pagina HTML salvata in 'debug_strumentimusicali.html' per analisi")
            return []
            
        logger.info(f"✅ Trovati {len(product_items)} prodotti nella pagina")
        
        # Limita il numero di prodotti da elaborare
        if len(product_items) > max_results * 2:
            product_items = product_items[:max_results * 2]
            logger.info(f"🔍 Limito i prodotti a {len(product_items)} per l'elaborazione")
    
    except Exception as e:
        logger.error(f"❌ Errore durante la ricerca: {str(e)}")
        BrowserManager.close_driver(driver)
        return []
    risultati = []
    processed = 0
    
    # Estrai i dettagli di ogni prodotto
    for item in product_items:
        if processed >= max_results:
            break
            
        try:
            processed += 1
            logger.info(f"\n📦 Elaborazione prodotto {processed}/{min(len(product_items), max_results)}")
            
            # Estrai i dati del prodotto in base alla struttura HTML specifica di Strumenti Musicali
            if item.name == 'tr' and 'productListing-even' in item.get('class', []) or 'productListing-odd' in item.get('class', []):
                try:
                    # Estrai il link e il nome del prodotto
                    product_link = item.select_one('td.productListing-data a')
                    if not product_link:
                        logger.warning("⚠️ Link prodotto non trovato, salto")
                        continue
                        
                    link = product_link.get('href', '')
                    if not link.startswith(('http', '//')):
                        link = urljoin(base_url, link)
                    
                    # Estrai il nome dal tag img alt o dal testo del link
                    img = product_link.select_one('img')
                    if img and img.get('alt'):
                        nome = img.get('alt')
                    else:
                        # Cerca il nome in altri elementi
                        nome_elem = product_link.select_one('.productName, .product-name, h2, h3, strong')
                        if nome_elem:
                            nome = nome_elem.get_text(strip=True)
                        else:
                            # Usa il testo del link come fallback
                            nome = product_link.get_text(strip=True).split('\n')[0].strip()
                    
                    # Pulisci il nome da eventuali caratteri speciali
                    nome = re.sub(r'\s+', ' ', nome).strip()
                    
                    # Controlla se il nome contiene le parole chiave
                    nome_lower = nome.lower()
                    if not any(parola in nome_lower for parola in parole_chiave):
                        logger.warning(f"⚠️ Parole chiave mancanti nel nome: {nome}, salto")
                        continue
                    
                    logger.info(f"🔠 Nome: {nome[:60]}..." if len(nome) > 60 else f"🔠 Nome: {nome}")
                    logger.info(f"🔗 Link: {link}")
                    
                    # Estrai l'immagine del prodotto
                    img_elem = item.select_one('img')
                    if img_elem:
                        img_url = img_elem.get('src', '')
                        if img_url and not img_url.startswith(('http', '//')):
                            img_url = urljoin(base_url, img_url)
                    else:
                        img_url = ''
                    
                    # Estrai il prezzo - cerca specificamente il formato del prezzo
                    price_text = item.get_text()
                    price_matches = re.findall(r'€\s*(\d+[\.,]\d{2})', price_text)
                    
                    if price_matches:
                        # Prendi il primo prezzo trovato
                        prezzo_testo = price_matches[0]
                        try:
                            # Converti in numero
                            prezzo_num = float(prezzo_testo.replace('.', '').replace(',', '.'))
                            
                            # Formatta il prezzo per la visualizzazione
                            prezzo_formattato = f"€{prezzo_num:,.2f}".replace(".", "X").replace(",", ".").replace("X", ",")
                            logger.info(f"💰 Prezzo: {prezzo_formattato}")
                        except ValueError:
                            logger.warning(f"⚠️ Impossibile convertire il prezzo: {prezzo_testo}")
                            continue
                    else:
                        logger.warning("⚠️ Prezzo non trovato, salto")
                        continue
                except Exception as e:
                    logger.error(f"❌ Errore nell'estrazione dei dati: {str(e)}")
                    continue
            else:
                # Per elementi non tabellari, usa i selettori standard
                # Estrai il nome del prodotto
                name_selectors = [
                    'a.productName', 'a.product-name', 'a.product-item-link',
                    'h2.product-name a', 'h3.product-item-name a',
                    'div.product-name a', 'a.product-item-name',
                    'h2.product-name', 'h3.product-item-name',
                    'a', 'span.productName'
                ]
                
                name_elem = None
                for selector in name_selectors:
                    try:
                        name_elem = item.select_one(selector)
                        if name_elem and name_elem.get_text(strip=True):
                            break
                    except:
                        continue
                
                if not name_elem:
                    logger.warning("⚠️ Nome prodotto non trovato, salto")
                    continue
                    
                nome = name_elem.get_text(strip=True)
                
                # Controlla se il nome contiene le parole chiave
                nome_lower = nome.lower()
                if not any(parola in nome_lower for parola in parole_chiave):
                    logger.warning(f"⚠️ Parole chiave mancanti nel nome: {nome}, salto")
                    continue
                
                logger.info(f"🔠 Nome: {nome[:60]}..." if len(nome) > 60 else f"🔠 Nome: {nome}")
                
                # Estrai il link se il nome è un link
                if name_elem.name == 'a' and name_elem.get('href'):
                    link = name_elem['href']
                    if not link.startswith(('http', '//')):
                        link = urljoin(base_url, link)
                else:
                    # Cerca un link nell'elemento
                    link_elem = item.find('a', href=True)
                    if link_elem:
                        link = link_elem['href']
                        if not link.startswith(('http', '//')):
                            link = urljoin(base_url, link)
                    else:
                        logger.warning("⚠️ Link prodotto non trovato, salto")
                        continue
                
                logger.info(f"🔗 Link: {link}")
                
                # Estrai il prezzo
                price_selectors = [
                    '.productSpecialPrice', '.productPrice',
                    'span.price', 'span.price-wrapper',
                    '[data-price-type="finalPrice"]',
                    'div.price-box', 'div.product-price',
                    'span[data-price-amount]', 'div.price-final_price',
                    'span[itemprop="price"]'
                ]
                
                price_elem = None
                for selector in price_selectors:
                    try:
                        price_elem = item.select_one(selector)
                        if price_elem and price_elem.get_text(strip=True):
                            break
                    except:
                        continue
                
                if not price_elem:
                    logger.warning("⚠️ Prezzo non trovato, salto")
                    continue
                    
                prezzo_testo = price_elem.get_text(strip=True)
                if not prezzo_testo:
                    logger.warning("⚠️ Testo del prezzo vuoto, salto")
                    continue
                prezzo_num = clean_price(prezzo_testo)
                
                if prezzo_num <= 0:
                    logger.warning(f"⚠️ Prezzo non valido: {prezzo_testo}, salto")
                    continue
                    
                # Formatta il prezzo per la visualizzazione
                prezzo_formattato = f"€{prezzo_num:,.2f}".replace(".", "X").replace(",", ".").replace("X", ",")
                logger.info(f"💰 Prezzo: {prezzo_formattato}")
                
                # Estrai l'immagine del prodotto
                img_selectors = [
                    'img.listingProductImage', 'img.productImage',
                    'img.product-image', 'img.product-image-photo',
                    'img[itemprop="image"]', 'img.photo.image',
                    'img.thumbnail', 'img', 'img:first-of-type'
                ]
                
                img_url = None
                for selector in img_selectors:
                    img_elem = item.select_one(selector)
                    if img_elem:
                        img_url = (
                            img_elem.get('src') or 
                            img_elem.get('data-src') or 
                            img_elem.get('data-srcset', '').split()[0] or
                            img_elem.get('data-original') or
                            img_elem.get('data-src-original')
                        )
                        if img_url:
                            break
                
            # Aggiungi il prodotto ai risultati
            
            # Estrazione prezzo originale (se presente)
            prezzo_originale = "N/A"
            prezzo_originale_num = 0.0
            
            try:
                # Cerca elementi che indicano un prezzo vecchio/barrato
                old_price_selectors = [
                    '.productOldPrice', '.old-price', '.regular-price', 
                    'span[data-price-type="oldPrice"]', 'span.old-price',
                    'strike', 'del', '.price-label'
                ]
                
                old_price_elem = None
                for selector in old_price_selectors:
                    old_price_elem = item.select_one(selector)
                    if old_price_elem:
                        break
                
                if old_price_elem:
                    old_price_text = old_price_elem.get_text(strip=True)
                    prezzo_originale_num = clean_price(old_price_text)
                    if prezzo_originale_num > 0:
                        prezzo_originale = f"€{prezzo_originale_num:,.2f}".replace(".", "X").replace(",", ".").replace("X", ",")
            except Exception as e:
                logger.warning(f"⚠️ Errore estrazione prezzo originale: {str(e)}")

            # Se non c'è prezzo originale o è 0, usa il prezzo attuale come base (nessuno sconto)
            if prezzo_originale_num == 0:
                prezzo_originale_num = prezzo_num

            prodotto_info = {
                "nome": nome,
                "prezzo": prezzo_formattato,  # Uniformato il nome della chiave agli altri scraper
                "prezzo_numerico": prezzo_num,
                "prezzo_originale": prezzo_originale,
                "prezzo_originale_numerico": prezzo_originale_num,
                "link": link,
                "immagine": img_url or "N/A",
                "descrizione": "",  # Possiamo estrarre la descrizione in un secondo momento se necessario
                "sito": "StrumentiMusicali.net"
            }
            
            risultati.append(prodotto_info)
            logger.info("✅ Prodotto aggiunto con successo")
            
        except Exception as e:
            logger.error(f"⚠️ Errore durante l'elaborazione del prodotto: {str(e)[:200]}")
            continue
    
    # Chiudi il driver Chrome alla fine dell'esecuzione
    BrowserManager.close_driver(driver)
    
    logger.info(f"\n✅ Ricerca completata. Trovati {len(risultati)} risultati validi")
    return sorted(risultati, key=lambda x: x['prezzo_numerico'])

def cerca_multiprodotti(lista_prodotti, num_processi=4):
    # Per ora restituiamo solo i risultati di una singola ricerca
    # Questa funzione può essere espansa per gestire più ricerche in parallelo
    if not lista_prodotti:
        return []
    return search_strumentimusicali(lista_prodotti[0])

# Esempio di utilizzo
if __name__ == "__main__":
    print("🔍 Test ricerca su StrumentiMusicali.net per 'eventide h90'")
    risultati = search_strumentimusicali("eventide h90")
    print("\n📊 Risultati trovati:")
    for i, r in enumerate(risultati, 1):
        print(f"{i}. {r['nome']} - {r['prezzo']} - {r['link']}")
