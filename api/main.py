"""FastAPI application entry point."""
import json
import threading
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path
from string import Template

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from api import i18n
from api.auth import require_admin
from api.routes import admin, analytics, contact, favicons, pricing, search
from config.database import init_db
from config.settings import settings
from config.sites_config import get_searchable_sites
from scrapers import relevance
from scheduler.jobs import build_scheduler
from utils.logger import get_logger

logger = get_logger(__name__)
_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Load the search model in the background, so the first search does not wait.
    threading.Thread(target=relevance._model, daemon=True).start()
    global _scheduler
    if settings.scheduler_enabled:
        _scheduler = build_scheduler()
        _scheduler.start()
        logger.info("scheduler started")
    yield
    if _scheduler:
        _scheduler.shutdown(wait=False)


app = FastAPI(title="INSTRINDER", version="0.2.1", lifespan=lifespan)
app.include_router(search.router)
app.include_router(contact.router)
app.include_router(pricing.router)
app.include_router(analytics.router)
app.include_router(admin.router)
app.include_router(favicons.router)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "web" / "static"), name="static")


@app.get("/health", tags=["health"])
def health():
    """Public liveness probe (page footer, Docker HEALTHCHECK, uptime monitors)."""
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False, dependencies=[Depends(require_admin)])
def metrics_endpoint():
    """Prometheus exposition format; needs the admin token."""
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(Path(__file__).parent / "web" / "static" / "favicon.svg", media_type="image/svg+xml")


_PAGE = Template((Path(__file__).parent / "web" / "index.html").read_text(encoding="utf-8"))


@app.get("/")
def root(request: Request):
    """JSON for API clients; the search page, in the visitor's language, for browsers."""
    if "text/html" not in request.headers.get("accept", ""):
        return {"service": "strumenti-musicali-scraper", "docs": "/docs"}

    lang, country = i18n.pick_language(request)
    t = i18n.TRANSLATIONS[lang]
    fields = {k: escape(v) for k, v in t.items()}
    fields["tagline"] = escape(t["tagline"].format(n=len(get_searchable_sites())))
    options = "".join(
        f'<option value="{code}"{" selected" if code == lang else ""}>'
        f"{escape(i18n.autonym(code))}</option>"
        for code in i18n.SUPPORTED
    )
    html = _PAGE.substitute(
        fields,
        lang=i18n.html_lang(lang),
        dir=i18n.text_direction(lang),
        language_options=options,
        version=app.version,
        # A shared ?q= link renders the results layout from the first paint.
        view="results" if request.query_params.get("q") else "home",
        strings=json.dumps(t, ensure_ascii=False).replace("</", "<\\/"),
    )
    resp = HTMLResponse(html, headers={
        "Content-Language": i18n.html_lang(lang),
        "Vary": "Accept, Accept-Language, Cookie, CF-IPCountry, X-Forwarded-For",
    })
    if country:
        resp.headers["X-Visitor-Country"] = country
    if request.query_params.get("lang") == lang:
        resp.set_cookie("lang", lang, max_age=365 * 86400, samesite="lax")
    return resp
