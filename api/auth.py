"""Access control for operator endpoints (/admin/*, /metrics).

A single shared secret, ADMIN_TOKEN in .env, sent as ``Authorization: Bearer
<token>`` or ``X-Admin-Token: <token>``. Secure by default: with no token
configured the operator endpoints are closed (403), never open.
"""
import hmac

from fastapi import Header, HTTPException

from config.settings import settings


def require_admin(
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
) -> None:
    expected = settings.admin_token
    if not expected:
        raise HTTPException(403, "admin API disabled: set ADMIN_TOKEN in .env")
    given = x_admin_token
    if not given and authorization and authorization.lower().startswith("bearer "):
        given = authorization[7:].strip()
    # Constant-time comparison: the response time must not leak the token.
    if not given or not hmac.compare_digest(given.encode(), expected.encode()):
        raise HTTPException(401, "missing or wrong admin token",
                            headers={"WWW-Authenticate": "Bearer"})
