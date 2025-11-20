from browser_manager import BrowserManager
import time

def debug_gear4music():
    url = "https://www.gear4music.it/it/search/?str_search_phrase=fender+stratocaster"
    driver = BrowserManager.create_driver()
    if not driver:
        print("Failed to create driver")
        return

    try:
        driver.get(url)
        time.sleep(5)
        with open("gear4music_debug.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("Saved gear4music_debug.html")
    finally:
        BrowserManager.close_driver(driver)

if __name__ == "__main__":
    debug_gear4music()
