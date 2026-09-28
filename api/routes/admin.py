"""Admin / monitoring endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from config.database import get_db
from config.sites_config import SITES_CONFIG
from models import Site
from monitoring.health_checker import check_all, check_site
from scheduler.jobs import scrape_priority, sync_sites

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/sites-status")
def sites_status(
    db: Session = Depends(get_db),
    area: str | None = Query(None, pattern="^(europe|usa|asia)$"),
    priority: int | None = Query(None, ge=1, le=3),
):
    db_sites = {s.site_key: s for s in db.query(Site).all()}
    out = []
    for key, cfg in SITES_CONFIG.items():
        if area and cfg["area"] != area:
            continue
        if priority and cfg["priority"] != priority:
            continue
        s = db_sites.get(key)
        out.append(
            {
                "site_key": key,
                "name": cfg["name"],
                "area": cfg["area"],
                "group": cfg["group"],
                "country": cfg["country"],
                "city": cfg["city"],
                "specialty": cfg["specialty"],
                "type": cfg["type"],
                "top": cfg["top"],
                "platform": cfg["platform"],
                "currency": cfg["currency"],
                "searchable": cfg["searchable"],
                "enabled": cfg["enabled"],
                "priority": cfg["priority"],
                "data_quality": cfg.get("data_quality"),
                "blocked_reason": cfg.get("blocked_reason"),
                "last_scrape": s.last_scrape.isoformat() if s and s.last_scrape else None,
                "scrape_status": s.scrape_status if s else "never",
                "error_count": s.error_count if s else 0,
            }
        )
    return out


@router.get("/coverage")
def coverage():
    """How much of the dataset the scraper can actually read, by area and tier."""
    total = len(SITES_CONFIG)
    usable = [c for c in SITES_CONFIG.values() if c["enabled"] and c["searchable"]]

    def group(field: str) -> dict:
        out: dict[str, dict] = {}
        for cfg in SITES_CONFIG.values():
            bucket = out.setdefault(str(cfg[field]), {"total": 0, "usable": 0})
            bucket["total"] += 1
            if cfg["enabled"] and cfg["searchable"]:
                bucket["usable"] += 1
        return out

    blocked: dict[str, int] = {}
    for cfg in SITES_CONFIG.values():
        if cfg.get("blocked_reason"):
            blocked[cfg["blocked_reason"]] = blocked.get(cfg["blocked_reason"], 0) + 1
    return {
        "stores_total": total,
        "stores_usable": len(usable),
        "by_area": group("area"),
        "by_priority": group("priority"),
        "by_platform": group("platform"),
        "blocked_reasons": blocked,
    }


@router.post("/sync-sites")
def sync():
    return {"synced": sync_sites()}


@router.post("/force-scrape")
def force_scrape(priority: int = Query(1, ge=1, le=3), query: str | None = None):
    return scrape_priority(priority, query=query)


@router.get("/health-check")
def health_check():
    return {"status": "ok"}


@router.get("/health-check/sites")
def health_check_sites(site_key: str | None = None):
    """Live reachability. One store with `site_key`, otherwise all of them."""
    if site_key:
        cfg = SITES_CONFIG.get(site_key)
        if not cfg:
            return {"error": f"unknown store: {site_key}"}
        return {site_key: check_site(cfg["url"])}
    results = check_all()
    return {
        "reachable": sum(1 for ok in results.values() if ok),
        "total": len(results),
        "sites": results,
    }
