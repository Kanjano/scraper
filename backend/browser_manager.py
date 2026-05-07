import os
import re
import time
import shutil
import tempfile
import subprocess
import threading
import logging
import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, NoSuchWindowException

logger = logging.getLogger("browser_manager")

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
    # Replace --disable-gpu (which can hurt detection) with --disable-software-rasterizer
    # to avoid GPU-software fallback while staying less detectable.
    options.add_argument("--disable-software-rasterizer")
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
        Serializza la creazione tra thread per evitare collisioni di porta/profilo.
        Tiene il lock anche durante un breve warmup (about:blank) per evitare
        che due UC patcher corrano sul binario di Chromium in parallelo."""
        user_data_dir = tempfile.mkdtemp(prefix="uc_profile_")

        def _build_kwargs():
            # Note: use_subprocess=True è stato rimosso — la modalità subprocess
            # di undetected_chromedriver è instabile con creazione parallela e
            # causa "no such window: target window already closed" sui driver
            # creati subito dopo il primo.
            kwargs = {
                "options": _build_options(headless, user_data_dir),
                "user_data_dir": user_data_dir,
            }
            if _CHROME_MAJOR:
                kwargs["version_main"] = _CHROME_MAJOR
            return kwargs

        try:
            with _DRIVER_CREATE_LOCK:
                driver = uc.Chrome(**_build_kwargs())
                # Warmup all'interno del lock per stabilizzare il driver prima
                # che un altro thread provi a patchare/avviare il proprio UC.
                try:
                    driver.set_page_load_timeout(45)
                    driver.set_script_timeout(45)
                    driver.get("about:blank")
                except Exception as warmup_exc:
                    logger.warning("Warmup driver fallito: %s", warmup_exc)
                time.sleep(0.5)
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
                    try:
                        driver.set_page_load_timeout(30)
                        driver.set_script_timeout(30)
                        driver.get("about:blank")
                    except Exception as warmup_exc:
                        logger.warning("Warmup driver (retry) fallito: %s", warmup_exc)
                    time.sleep(0.5)
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

    @staticmethod
    def fetch_html(url: str, wait_seconds: float = 2.0,
                   post_load_callback=None, retries: int = 1,
                   site_label: str = "") -> str:
        """Fetch HTML per uno scraper Selenium con retry resiliente.

        Crea un driver, naviga all'URL, aspetta `wait_seconds`, esegue
        opzionalmente `post_load_callback(driver)` (es. scroll loop),
        legge `driver.page_source`, e chiude il driver.

        Cattura `NoSuchWindowException` / `WebDriverException` durante
        get/page_source e ricrea il driver per un secondo tentativo.

        Returns:
            HTML come stringa, oppure None su fallimento totale.
        """
        label = f"[{site_label}] " if site_label else ""
        last_error = None

        for attempt in range(retries + 1):
            # Backoff progressivo tra i tentativi per dare tempo a un altro
            # thread di completare la creazione del proprio driver UC.
            if attempt > 0:
                time.sleep(1.5 * attempt)
            driver = BrowserManager.create_driver()
            if not driver:
                last_error = "create_driver returned None"
                logger.warning("%sfetch_html attempt %d: driver creation failed",
                               label, attempt + 1)
                continue

            try:
                driver.get(url)
                if wait_seconds and wait_seconds > 0:
                    time.sleep(wait_seconds)
                if post_load_callback is not None:
                    try:
                        post_load_callback(driver)
                    except (NoSuchWindowException, WebDriverException) as cb_exc:
                        # Errore di finestra già chiusa durante callback — ritenta.
                        last_error = f"callback: {cb_exc}"
                        logger.warning("%sfetch_html attempt %d post_load_callback error: %s",
                                       label, attempt + 1, str(cb_exc)[:200])
                        BrowserManager.close_driver(driver)
                        driver = None
                        continue
                html = driver.page_source
                BrowserManager.close_driver(driver)
                return html
            except (NoSuchWindowException, WebDriverException) as exc:
                last_error = str(exc)
                logger.warning("%sfetch_html attempt %d WebDriver error: %s",
                               label, attempt + 1, str(exc)[:200])
                BrowserManager.close_driver(driver)
                driver = None
                continue
            except Exception as exc:
                last_error = str(exc)
                logger.warning("%sfetch_html attempt %d unexpected error: %s",
                               label, attempt + 1, str(exc)[:200])
                BrowserManager.close_driver(driver)
                driver = None
                continue

        logger.error("%sfetch_html: tutti i tentativi falliti — ultimo errore: %s",
                     label, str(last_error)[:200] if last_error else "n/a")
        return None
