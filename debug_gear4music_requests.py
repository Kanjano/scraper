import requests

def debug_gear4music_requests():
    url = "https://www.gear4music.it/it/search/?str_search_phrase=fender+stratocaster"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        with open("gear4music_debug.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        print("Saved gear4music_debug.html")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_gear4music_requests()
