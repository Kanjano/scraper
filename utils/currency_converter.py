"""Currency conversion to a base currency (EUR).

Uses a free no-key endpoint (open.er-api.com) with in-memory caching and a
static fallback table so the system degrades gracefully when offline.
"""
import time

import requests

from utils.logger import get_logger

logger = get_logger(__name__)

# Units of currency per 1 EUR. Covers every currency in config/stores.json plus
# CAD/AUD. Only a fallback: live rates are fetched and cached at runtime.
_FALLBACK_RATES = {
    "EUR": 1.0,
    "USD": 1.08,
    "GBP": 0.85,
    "CHF": 0.95,
    "CZK": 25.0,
    "JPY": 165.0,
    "HKD": 8.45,
    "SGD": 1.45,
    "INR": 90.0,
    "AED": 3.97,
    "TRY": 38.0,
    "KRW": 1450.0,
    "CAD": 1.47,
    "AUD": 1.63,
}
_CACHE_TTL = 6 * 3600


class CurrencyConverter:
    def __init__(self, base: str = "EUR"):
        self.base = base.upper()
        self._rates: dict[str, float] = dict(_FALLBACK_RATES)
        self._fetched_at = 0.0

    def _refresh(self) -> None:
        if time.time() - self._fetched_at < _CACHE_TTL:
            return
        try:
            resp = requests.get(f"https://open.er-api.com/v6/latest/{self.base}", timeout=10)
            resp.raise_for_status()
            rates = resp.json().get("rates")
            if rates:
                self._rates = rates
                self._fetched_at = time.time()
        except Exception as exc:  # noqa: BLE001
            logger.warning("currency refresh failed, using fallback", extra={"error": str(exc)})

    def to_base(self, amount: float, from_currency: str) -> float:
        from_currency = from_currency.upper()
        if from_currency == self.base:
            return round(amount, 2)
        self._refresh()
        rate = self._rates.get(from_currency)
        if not rate:
            logger.warning("no rate for %s, returning unconverted", from_currency)
            return round(amount, 2)
        return round(amount / rate, 2)


converter = CurrencyConverter()
