from scraper_thomann import cerca_thomann
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

query = "fender stratocaster custom shop"
print(f"Testing Thomann scraper with query: '{query}'")

results = cerca_thomann(query)

print(f"Found {len(results)} results.")
for r in results:
    print(f"- {r['nome']} ({r['prezzo']})")
