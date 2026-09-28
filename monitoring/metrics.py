"""Prometheus metrics, exposed at GET /metrics (admin token required).

Recorded by the orchestrator (per shop and per search) and the contact form.
Optional — degrades to no-ops if prometheus_client is missing.
"""
try:
    from prometheus_client import Counter, Histogram

    SCRAPE_COUNT = Counter("instrinder_scrape_total", "Shop searches by outcome",
                           ["site", "status"])  # status: ok | empty | error
    SCRAPE_LATENCY = Histogram("instrinder_scrape_seconds", "Time to search one shop", ["site"],
                               buckets=(1, 2, 5, 10, 20, 30, 60, 120, 300))
    SEARCH_COUNT = Counter("instrinder_search_total", "Searches run", ["translated"])
    SEARCH_LATENCY = Histogram("instrinder_search_seconds", "Time to answer a whole search",
                               buckets=(5, 15, 30, 60, 120, 180, 300, 600))
    SEARCH_RESULTS = Histogram("instrinder_search_results", "Relevant offers per search",
                               buckets=(0, 1, 10, 50, 100, 250, 500, 1000))
    CONTACT_COUNT = Counter("instrinder_contact_total", "Contact form submissions", ["result"])
    AVAILABLE = True
except ImportError:  # pragma: no cover
    AVAILABLE = False

    class _Noop:
        def labels(self, *a, **k):
            return self

        def inc(self, *a, **k):
            ...

        def observe(self, *a, **k):
            ...

    SCRAPE_COUNT = SCRAPE_LATENCY = _Noop()
    SEARCH_COUNT = SEARCH_LATENCY = SEARCH_RESULTS = CONTACT_COUNT = _Noop()
