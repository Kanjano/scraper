from fastapi.testclient import TestClient

from api.main import app


def test_root():
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["service"] == "strumenti-musicali-scraper"


def test_pricing_endpoint():
    with TestClient(app) as client:
        r = client.post(
            "/pricing",
            json=[
                {"site": "A", "price_eur": 100, "reviews": 10, "stock": 5},
                {"site": "B", "price_eur": 120, "reviews": 5, "stock": 2},
            ],
        )
        assert r.status_code == 200
        assert r.json()["lowest_price_site"] == "A"


def test_admin_health():
    with TestClient(app) as client:
        assert client.get("/admin/health-check").json() == {"status": "ok"}


def test_search_stream_sends_progress_then_the_final_result(monkeypatch):
    import json

    from api.routes import search as search_route

    def fake(query, on_event=None, cancel=None, **kw):
        on_event("phase", {"id": "search", "status": "active"})
        on_event("site", {"key": "thomann", "status": "ok", "relevant": [], "done": 1, "total": 1})
        return {"query": query, "total_results": 0, "results": []}

    monkeypatch.setattr(search_route.orchestrator, "search_all_sites", fake)
    with TestClient(app) as client:
        r = client.get("/search/stream", params={"query": "moog"})
    assert r.headers["content-type"].startswith("text/event-stream")
    events = [line[7:] for line in r.text.splitlines() if line.startswith("event: ")]
    assert events == ["phase", "site", "done"]
    done = r.text.split("event: done\ndata: ")[1].split("\n")[0]
    assert json.loads(done)["query"] == "moog"


def test_favicon_falls_back_to_a_letter_badge(monkeypatch, tmp_path):
    from api.routes import favicons

    monkeypatch.setattr(favicons, "CACHE", tmp_path)
    monkeypatch.setattr(favicons, "_fetch_icon", lambda url: None)
    with TestClient(app) as client:
        r = client.get("/favicon/thomann")
        assert r.status_code == 200 and r.headers["content-type"] == "image/svg+xml"
        assert b">T</text>" in r.content
        assert client.get("/favicon/not-a-shop").status_code == 404


def _contact_config(monkeypatch, **over):
    from api.routes import contact as contact_route

    base = dict(contact_email="owner@example.org", smtp_host="smtp.example.org", smtp_port=587,
                smtp_user="bot@example.org", smtp_password="x", smtp_security="starttls",
                contact_from="", contact_rate_limit=2, contact_rate_window_s=600)
    base.update(over)
    for k, v in base.items():
        monkeypatch.setattr(contact_route.settings, k, v)
    contact_route._recent.clear()
    sent = []
    monkeypatch.setattr(contact_route, "_send", sent.append)
    return sent


GOOD = {"name": "Ada", "email": "ada@example.com", "message": "Please add a shop in Milan."}


def test_contact_sends_to_the_configured_address(monkeypatch):
    sent = _contact_config(monkeypatch)
    with TestClient(app) as client:
        r = client.post("/contact", json=GOOD)
    assert r.status_code == 200
    [msg] = sent
    assert msg["To"] == "owner@example.org" and msg["Reply-To"] == "ada@example.com"
    assert "Please add a shop" in msg.get_content()


def test_contact_address_never_reaches_the_page(monkeypatch):
    _contact_config(monkeypatch)
    with TestClient(app) as client:
        page = client.get("/", headers={"accept": "text/html"}).text
    assert "owner@example.org" not in page


def test_contact_rejects_bad_input_bots_and_floods(monkeypatch):
    sent = _contact_config(monkeypatch)
    with TestClient(app) as client:
        assert client.post("/contact", json={**GOOD, "email": "x@y\nBcc: a@b.co"}).status_code == 422
        assert client.post("/contact", json={**GOOD, "name": "A\r\nBcc: x"}).status_code == 422
        assert client.post("/contact", json={**GOOD, "message": "hi"}).status_code == 422
        assert client.post("/contact", json={**GOOD, "website": "http://spam"}).status_code == 200
        assert sent == []  # the honeypot answer is silent
        assert client.post("/contact", json=GOOD).status_code == 200
        assert client.post("/contact", json=GOOD).status_code == 200
        assert client.post("/contact", json=GOOD).status_code == 429  # limit is 2 here


def test_contact_unconfigured_is_503(monkeypatch):
    _contact_config(monkeypatch, contact_email="")
    with TestClient(app) as client:
        assert client.post("/contact", json=GOOD).status_code == 503
