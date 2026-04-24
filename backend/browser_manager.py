import os
import time
import shutil
import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

class BrowserManager:
    @staticmethod
    def create_driver(headless=True):
        """Crea e restituisce una nuova istanza del driver."""
        options = uc.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        try:
            driver = uc.Chrome(options=options, use_subprocess=True, version_main=145)
            driver.set_page_load_timeout(30)
            driver.set_script_timeout(30)
            return driver
        except Exception as e:
            print(f"⚠️ Errore creazione driver: {e}")
            # Tentativo di pulizia cache e retry
            BrowserManager.cleanup_cache()
            try:
                # Ricreiamo le opzioni perché non possono essere riutilizzate
                options = uc.ChromeOptions()
                if headless:
                    options.add_argument("--headless=new")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1920,1080")
                options.add_argument("--disable-blink-features=AutomationControlled")
                
                driver = uc.Chrome(options=options, use_subprocess=True, version_main=145)
                driver.set_page_load_timeout(30)
                driver.set_script_timeout(30)
                return driver
            except Exception as e2:
                print(f"❌ Errore fatale creazione driver: {e2}")
                return None

    @staticmethod
    def cleanup_cache():
        """Pulisce la cache di undetected_chromedriver"""
        cache_dir = os.path.expanduser('~/Library/Application Support/undetected_chromedriver')
        if os.path.exists(cache_dir):
            try:
                shutil.rmtree(cache_dir)
                print("✅ Cache driver pulita")
            except Exception as e:
                print(f"⚠️ Errore pulizia cache: {e}")

    @staticmethod
    def close_driver(driver):
        """Chiude il driver in modo sicuro."""
        if driver:
            try:
                driver.quit()
            except:
                pass

