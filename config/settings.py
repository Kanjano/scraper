"""Global configuration loaded from environment (.env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "sqlite:///./data/instruments.db"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    # Scraping
    scraper_contact: str = ""            # e-mail/URL added to the scraper's User-Agent
    default_timeout: int = 30
    max_retries: int = 3
    headless_browser: bool = True
    # Browser for "stealth" shops: "chrome" (installed Google Chrome, amd64/macOS)
    # or "" for patchright's bundled Chromium (e.g. Linux arm64, where Chrome is
    # not available).
    stealth_browser_channel: str = "chrome"
    browser_pool_size: int = 5

    # Proxy
    use_proxy: bool = False
    proxy_list: str = ""

    # Rate limiting
    default_delay_between_requests: float = 3.0
    requests_per_minute_default: int = 10

    # Visitor geolocation (page language). Optional DB-IP Lite country file.
    geoip_db: str = "data/dbip-country-lite.mmdb"

    # Search relevance: local multilingual embedding model (downloaded once into
    # models_dir, then offline). Empty = literal word matching only.
    semantic_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    models_dir: str = "data/models"

    # Contact form. The recipient is configuration, never page content: set it
    # in .env (CONTACT_EMAIL) together with an SMTP account that may send mail.
    # Empty CONTACT_EMAIL or SMTP_HOST = form answers "not available" (HTTP 503).
    contact_email: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_security: str = "starttls"      # starttls | ssl | none
    contact_from: str = ""               # sender address; defaults to smtp_user
    contact_rate_limit: int = 3          # messages per client IP ...
    contact_rate_window_s: int = 600     # ... in this many seconds

    # Currency
    currency_api_key: str = ""
    base_currency: str = "EUR"

    # Site APIs / keys
    reverb_api_key: str = ""

    # Pricing
    margin_min_percent: float = 5.0
    margin_max_percent: float = 15.0
    price_discount_multiplier: float = 0.93

    # Cache
    cache_enabled: bool = True
    cache_ttl_hours: int = 12

    # Scheduler
    scheduler_enabled: bool = True
    timezone: str = "Europe/Rome"

    @property
    def proxies(self) -> list[str]:
        return [p.strip() for p in self.proxy_list.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
