"""Prometheus metrics. Optional — degrades to no-ops if client missing."""
try:
    from prometheus_client import Counter, Histogram

    SCRAPE_COUNT = Counter("scrape_total", "Total scrape attempts", ["site", "status"])
    SCRAPE_LATENCY = Histogram("scrape_latency_seconds", "Scrape latency", ["site"])
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

    SCRAPE_COUNT = _Noop()
    SCRAPE_LATENCY = _Noop()
