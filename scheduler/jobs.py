"""APScheduler job definitions + scheduler factory.

Sync the 120-store dataset into the `sites` table, then scrape by priority:
priority 1 (global majors) most often, priority 3 (niche shops and workshops)
rarely. Only stores with a working search route are scraped; blocked ones keep
their reason in the database so the admin API can show why.
"""
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from config.database import SessionLocal
from config.settings import settings
from config.sites_config import SITES_CONFIG, get_searchable_sites
from models import Site
from monitoring.health_checker import check_all
from scheduler.orchestrator import ScraperOrchestrator
from utils.logger import get_logger

logger = get_logger(__name__)
orchestrator = ScraperOrchestrator()

# Queries used by the scheduled sweeps: broad enough to land results in both
# generalist and specialist shops.
DEFAULT_QUERIES = ("fender stratocaster", "gibson les paul", "yamaha")


def sync_sites() -> int:
    """Upsert every dataset store into the `sites` table. Returns the count."""
    db = SessionLocal()
    try:
        for key, cfg in SITES_CONFIG.items():
            site = db.query(Site).filter_by(site_key=key).one_or_none()
            if not site:
                site = Site(site_key=key)
                db.add(site)
            site.name = cfg["name"]
            site.url = cfg["url"]
            site.country = cfg["country"]
            site.area = cfg["area"]
            site.group_name = cfg["group"]
            site.city = cfg["city"]
            site.specialty = cfg["specialty"]
            site.store_type = cfg["type"]
            site.top = cfg["top"]
            site.platform = cfg["platform"]
            site.currency = cfg["currency"]
            site.enabled = cfg["enabled"]
            site.priority = cfg["priority"]
            site.blocked_reason = cfg.get("blocked_reason")
            if not site.scrape_status:
                site.scrape_status = "pending"
        db.commit()
        return len(SITES_CONFIG)
    finally:
        db.close()


def _record_result(site_key: str, status: str, found: int) -> None:
    db = SessionLocal()
    try:
        site = db.query(Site).filter_by(site_key=site_key).one_or_none()
        if not site:
            return
        site.last_scrape = datetime.utcnow()
        site.scrape_status = status
        if status != "success":
            site.error_count = (site.error_count or 0) + 1
        db.commit()
    finally:
        db.close()


def scrape_priority(priority: int, query: str | None = None) -> dict:
    """Scrape every searchable store of one priority tier."""
    keys = list(get_searchable_sites(priority=priority).keys())
    if not keys:
        logger.info("priority %d: no searchable sites", priority)
        return {"priority": priority, "sites": 0}

    queries = [query] if query else list(DEFAULT_QUERIES)
    totals = {}
    for q in queries:
        result = orchestrator.search_all_sites(q, sites=keys)
        per_site = {}
        for offer in result["results"]:
            per_site[offer["site"]] = per_site.get(offer["site"], 0) + 1
        totals[q] = result["total_results"]
        names = {SITES_CONFIG[k]["name"]: k for k in keys}
        for name, key in names.items():
            found = per_site.get(name, 0)
            _record_result(key, "success" if found else "empty", found)
    logger.info("priority %d scraped: %s", priority, totals)
    return {"priority": priority, "sites": len(keys), "results": totals}


def health_check_all_sites() -> dict[str, bool]:
    result = check_all()
    down = [k for k, ok in result.items() if not ok]
    logger.info("health check: %d/%d reachable", len(result) - len(down), len(result))
    return result


def build_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone=settings.timezone)
    sched.add_job(sync_sites, "date", id="sync-sites")  # once at startup
    sched.add_job(scrape_priority, "interval", hours=4, args=[1], id="p1")
    sched.add_job(scrape_priority, "interval", hours=12, args=[2], id="p2")
    sched.add_job(scrape_priority, "interval", hours=24, args=[3], id="p3")
    sched.add_job(health_check_all_sites, "interval", hours=6, id="health")
    return sched
