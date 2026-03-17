"""
CSRF protection middleware using the double-submit cookie pattern.

For cookie-authenticated requests (bond_session present, no Bearer header),
state-changing methods (POST, PUT, DELETE, PATCH) must include an
X-CSRF-Token header whose value matches the bond_csrf cookie.

Bearer-authenticated requests and safe methods (GET, HEAD, OPTIONS) are exempt.
The /auth/token and /health endpoints are also exempt.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
import logging

LOGGER = logging.getLogger(__name__)

# Endpoints exempt from CSRF checks
CSRF_EXEMPT_PATHS = {"/auth/token", "/health"}

# HTTP methods that are considered state-changing
STATE_CHANGING_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Only check state-changing methods
        if request.method not in STATE_CHANGING_METHODS:
            return await call_next(request)

        # Skip exempt paths (use endswith to handle potential prefix stripping)
        path = request.url.path
        if any(path == p or path.endswith(p) for p in CSRF_EXEMPT_PATHS):
            return await call_next(request)

        # Skip if Bearer auth is present (mobile / API clients)
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            return await call_next(request)

        # Only enforce CSRF if cookie auth is being used
        bond_session = request.cookies.get("bond_session")
        if not bond_session:
            # No cookie auth — let the downstream auth dependency handle 401
            return await call_next(request)

        # Cookie auth present — validate CSRF
        csrf_cookie = request.cookies.get("bond_csrf")
        csrf_header = request.headers.get("x-csrf-token")

        if not csrf_cookie or not csrf_header:
            LOGGER.warning(f"CSRF validation failed: missing token for {request.method} {request.url.path}")
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF validation failed: missing X-CSRF-Token header or bond_csrf cookie."},
            )

        if csrf_cookie != csrf_header:
            LOGGER.warning(f"CSRF validation failed: token mismatch for {request.method} {request.url.path}")
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF validation failed: X-CSRF-Token header does not match bond_csrf cookie."},
            )

        return await call_next(request)
