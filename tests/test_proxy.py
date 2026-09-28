from utils.proxy_manager import ProxyManager


def test_disabled_returns_none():
    pm = ProxyManager(proxies=[], enabled=False)
    assert pm.active is False
    assert pm.next_proxy() is None
    assert pm.as_requests() is None


def test_enabled_but_empty_disables():
    pm = ProxyManager(proxies=[], enabled=True)
    assert pm.active is False


def test_round_robin_rotation():
    pm = ProxyManager(proxies=["1.1.1.1:8080", "2.2.2.2:8080"], enabled=True)
    a = pm.next_proxy()
    b = pm.next_proxy()
    c = pm.next_proxy()
    assert a != b
    assert a == c  # wraps around
    assert a.startswith("http://")  # scheme defaulted


def test_requests_shape():
    pm = ProxyManager(proxies=["user:pass@host:3128"], enabled=True)
    req = pm.as_requests()
    assert req == {"http": "http://user:pass@host:3128", "https": "http://user:pass@host:3128"}


def test_playwright_shape_with_auth():
    pw = ProxyManager.as_playwright("http://bob:secret@proxy.example.com:8000")
    assert pw == {
        "server": "http://proxy.example.com:8000",
        "username": "bob",
        "password": "secret",
    }


def test_playwright_shape_no_auth():
    pw = ProxyManager.as_playwright("socks5://10.0.0.1:1080")
    assert pw == {"server": "socks5://10.0.0.1:1080"}


def test_playwright_none():
    assert ProxyManager.as_playwright(None) is None
