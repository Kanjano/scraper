import os
import time
import atexit
import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

class BrowserManager:
    _instance = None
    _driver = None
    _usage_count = 0

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BrowserManager, cls).__new__(cls)
            atexit.register(cls.cleanup)
        return cls._instance

    @classmethod
    def get_driver(cls):
        if cls._driver is None:
            cls._initialize_driver()
        cls._usage_count += 1
        return cls._driver

    @classmethod
    def release_driver(cls):
        if cls._usage_count > 0:
            cls._usage_count -= 1
        if cls._usage_count == 0 and cls._driver is not None:
            cls.cleanup()

    @classmethod
    def _initialize_driver(cls, max_retries=3):
        for attempt in range(max_retries):
            try:
                # Pulisci la cache prima di inizializzare
                if attempt > 0:
                    cls._cleanup_cache()
                
                # Configurazione minima essenziale
                options = uc.ChromeOptions()
                options.add_argument("--headless=new")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1920,1080")
                
                # Disabilita il banner di automazione
                options.add_argument("--disable-blink-features=AutomationControlled")
                
                # Configura il driver con meno opzioni possibili
                try:
                    # Rimuovi version_main per lasciare che undetected_chromedriver rilevi automaticamente la versione
                    cls._driver = uc.Chrome(
                        options=options,
                        use_subprocess=True,
                        driver_executable_path=None,
                        browser_executable_path=None
                    )
                except Exception as e:
                    print(f"⚠️ Errore nell'inizializzazione del driver: {str(e)[:200]}")
                    # Se fallisce, prova a forzare il download
                    print("⚠️ Provo a forzare il download del driver...")
                    import shutil
                    import os
                    cache_dir = os.path.expanduser("~/Library/Application Support/undetected_chromedriver")
                    if os.path.exists(cache_dir):
                        shutil.rmtree(cache_dir)
                    
                    # Prova di nuovo con la versione automatica
                    cls._driver = uc.Chrome(
                        options=options,
                        use_subprocess=True
                    )
                
                # Imposta timeout ragionevoli
                cls._driver.set_page_load_timeout(30)
                cls._driver.set_script_timeout(30)
                
                return
                
            except Exception as e:
                print(f"⚠️ Tentativo {attempt + 1} fallito: {str(e)[:200]}...")  # Limita la lunghezza dell'errore
                if attempt == max_retries - 1:
                    cls._cleanup_cache()
                    raise Exception("Impossibile inizializzare il browser dopo diversi tentativi")
                time.sleep(2)  # Attendi prima di riprovare
    
    @classmethod
    def _cleanup_cache(cls):
        """Pulisce la cache di undetected_chromedriver"""
        import shutil
        import os
        cache_dir = os.path.expanduser('~/Library/Application Support/undetected_chromedriver')
        if os.path.exists(cache_dir):
            print("⚠️ Pulizia della cache del driver...")
            try:
                shutil.rmtree(cache_dir)
                print("✅ Cache pulita con successo")
            except Exception as e:
                print(f"❌ Errore durante la pulizia della cache: {e}")

    @classmethod
    def cleanup(cls):
        if cls._driver is not None:
            try:
                cls._driver.quit()
            except:
                pass
            finally:
                cls._driver = None

# Funzioni di utilità per gli scraper
def with_browser(func):
    """Decoratore per gestire automaticamente il ciclo di vita del browser"""
    def wrapper(*args, **kwargs):
        driver = BrowserManager.get_driver()
        try:
            return func(driver, *args, **kwargs)
        finally:
            BrowserManager.release_driver()
    return wrapper
