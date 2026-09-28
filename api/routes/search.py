"""Search / comparison endpoints."""
import json
import queue
import threading

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from api.schemas import SearchResponse
from config.sites_config import SITES_CONFIG
from scheduler.orchestrator import ScraperOrchestrator

router = APIRouter(tags=["search"])
orchestrator = ScraperOrchestrator()


@router.get("/search", response_model=SearchResponse)
def search(
    query: str = Query(..., min_length=1),
    limit: int = 20,
    priority: int | None = Query(None, ge=1, le=3, description="1=global majors"),
    area: str | None = Query(None, pattern="^(europe|usa|asia)$"),
    sites: str | None = Query(None, description="comma-separated store ids"),
):
    """Search every searchable store, ranked by EUR price. Filter by tier/area."""
    keys = [s.strip() for s in sites.split(",")] if sites else None
    return orchestrator.search_all_sites(
        query, sites=keys, limit=limit, priority=priority, area=area
    )


@router.get("/search/stream")
def search_stream(
    query: str = Query(..., min_length=1),
    limit: int = 20,
    priority: int | None = Query(None, ge=1, le=3),
    area: str | None = Query(None, pattern="^(europe|usa|asia)$"),
    sites: str | None = Query(None, description="comma-separated store ids"),
):
    """Same search as ``/search``, streamed as Server-Sent Events while it runs.

    Events: ``phase`` {id: prepare|search|filter|rank, status: active|done},
    ``start`` {query, translated_query, sites: [...]}, ``site`` {key, name,
    status: ok|empty|error, offers, relevant: [offers], done, total},
    ``done`` (the ``/search`` response, ranked), ``error`` {message}.
    Closing the connection stops shops that have not started yet.
    """
    keys = [s.strip() for s in sites.split(",")] if sites else None
    events: queue.Queue = queue.Queue()
    cancel = threading.Event()

    def emit(kind: str, data) -> None:
        events.put((kind, data))

    def work() -> None:
        try:
            final = orchestrator.search_all_sites(
                query, sites=keys, limit=limit, priority=priority, area=area,
                on_event=emit, cancel=cancel,
            )
            emit("done", final)
        except Exception as exc:  # noqa: BLE001 — reported to the client
            emit("error", {"message": f"{type(exc).__name__}: {exc}"[:300]})
        finally:
            events.put(None)

    threading.Thread(target=work, daemon=True).start()

    def stream():
        try:
            while True:
                try:
                    item = events.get(timeout=15)
                except queue.Empty:
                    yield ": keep-alive\n\n"  # proxies drop idle connections
                    continue
                if item is None:
                    return
                kind, data = item
                yield f"event: {kind}\ndata: {json.dumps(data, default=str)}\n\n"
        finally:
            cancel.set()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/search-all-sites", response_model=SearchResponse)
def search_all_sites(query: str = Query(..., min_length=1), limit: int = 20):
    return orchestrator.search_all_sites(query, limit=limit)


@router.get("/stores")
def stores(
    area: str | None = Query(None, pattern="^(europe|usa|asia)$"),
    specialty: str | None = None,
    searchable_only: bool = False,
):
    """The store dataset as configured, with each store's scraping state."""
    out = []
    for key, cfg in SITES_CONFIG.items():
        if area and cfg["area"] != area:
            continue
        if specialty and cfg["specialty"] != specialty:
            continue
        if searchable_only and not (cfg["searchable"] and cfg["enabled"]):
            continue
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
                "url": cfg["url"],
                "currency": cfg["currency"],
                "platform": cfg["platform"],
                "priority": cfg["priority"],
                "searchable": cfg["searchable"],
                "enabled": cfg["enabled"],
                "blocked_reason": cfg.get("blocked_reason"),
            }
        )
    return {"total": len(out), "stores": out}
