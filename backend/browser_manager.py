import os
import re
import time
import shutil
import tempfile
import subprocess
import threading
import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

_DRIVER_CREATE_LOCK = threading.Lock()


def _detect_chrome_major_version():
    """Detect installed Chrome major version dynamically."""
    env_override = os.environ.get("CHROME_VERSION_MAIN")
    if env_override and env_override.isdigit():
        return int(env_override)

    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "google-chrome",
        "chromium",
    ]
    for path in candidates:
        try:
            out = subprocess.run(
                [path, "--version"],
                capture_output=True, text=True, timeout=5
            )
            text = (out.stdout or out.stderr or "").strip()
            m = re.search(r"(\d+)\.\d+\.\d+", text)
            if m:
                return int(m.group(1))
        except Exception:
            continue
    return None


_CHROME_MAJOR = _detect_chrome_major_version()


def _build_options(headless: bool, user_data_dir: str) -> uc.ChromeOptions:
    options = uc.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=it-IT")
    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    )
    return options


class BrowserManager:
    @staticmethod
    def create_driver(headless=True):
        """Crea e restituisce una nuova istanza del driver con user-data-dir univoco.
        Serializza la creazione tra thread per evitare collisioni di porta/profilo."""
        user_data_dir = tempfile.mkdtemp(prefix="uc_profile_")

        def _build_kwargs():
            kwargs = {
                "options": _build_options(headless, user_data_dir),
                "use_subprocess": True,
                "user_data_dir": user_data_dir,
            }
            if _CHROME_MAJOR:
                kwargs["version_main"] = _CHROME_MAJOR
            return kwargs

        try:
            with _DRIVER_CREATE_LOCK:
                driver = uc.Chrome(**_build_kwargs())
                time.sleep(1.5)
            driver.set_page_load_timeout(45)
            driver.set_script_timeout(45)
            driver._uc_user_data_dir = user_data_dir
            return driver
        except Exception as e:
            print(f"⚠️ Errore creazione driver: {e}")
            try:
                shutil.rmtree(user_data_dir, ignore_errors=True)
            except Exception:
                pass
            user_data_dir = tempfile.mkdtemp(prefix="uc_profile_")
            try:
                with _DRIVER_CREATE_LOCK:
                    driver = uc.Chrome(**_build_kwargs())
                driver.set_page_load_timeout(30)
                driver.set_script_timeout(30)
                driver._uc_user_data_dir = user_data_dir
                return driver
            except Exception as e2:
                print(f"❌ Errore fatale creazione driver: {e2}")
                shutil.rmtree(user_data_dir, ignore_errors=True)
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
        """Chiude il driver in modo sicuro e rimuove user-data-dir associato."""
        if driver:
            user_data_dir = getattr(driver, "_uc_user_data_dir", None)
            try:
                driver.quit()
            except Exception:
                pass
            if user_data_dir:
                shutil.rmtree(user_data_dir, ignore_errors=True)

