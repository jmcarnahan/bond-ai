"""
Structured audit logging middleware for security-relevant operations.

Logs authentication events, REST state-changing operations, and request
metadata in a structured format suitable for CloudWatch Logs ingestion
and metric filter creation.

Log format: AUDIT_{EVENT_TYPE}: key=value key=value ...

Event types:
- AUDIT_AUTH_SUCCESS: Successful authentication (per request)
- AUDIT_AUTH_FAILURE: Failed authentication attempt
- AUDIT_STATE_CHANGE: State-changing REST operation (POST/PUT/DELETE/PATCH)
- AUDIT_ACCESS_DENIED: 403 Forbidden responses

MCP tool invocations are logged separately in BedrockAgent.py using
the MCP_TOOL_INVOCATION/MCP_TOOL_RESULT format (T9/T21).
"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

AUDIT_LOGGER = logging.getLogger("bondable.audit")

STATE_CHANGING_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

# Paths to exclude from audit logging (high-frequency, low-value)
AUDIT_EXCLUDE_PATHS = {"/health", "/providers"}


class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Skip noisy endpoints
        if path in AUDIT_EXCLUDE_PATHS:
            return await call_next(request)

        start_time = time.time()
        client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
        method = request.method
        user_agent = request.headers.get("user-agent", "")[:100]

        # Detect auth method
        has_bearer = bool(request.headers.get("authorization", "").lower().startswith("bearer "))
        has_cookie = bool(request.cookies.get("bond_session"))
        auth_method = "bearer" if has_bearer else ("cookie" if has_cookie else "none")

        response = await call_next(request)

        duration_ms = int((time.time() - start_time) * 1000)
        status_code = response.status_code

        # Log authentication failures
        if status_code == 401:
            AUDIT_LOGGER.warning(
                "AUDIT_AUTH_FAILURE: method=%s path=%s ip=%s auth_method=%s status=%d duration_ms=%d",
                method, path, client_ip, auth_method, status_code, duration_ms
            )
        # Log access denied
        elif status_code == 403:
            AUDIT_LOGGER.warning(
                "AUDIT_ACCESS_DENIED: method=%s path=%s ip=%s auth_method=%s status=%d duration_ms=%d",
                method, path, client_ip, auth_method, status_code, duration_ms
            )
        # Log state-changing operations
        elif method in STATE_CHANGING_METHODS:
            AUDIT_LOGGER.info(
                "AUDIT_STATE_CHANGE: method=%s path=%s ip=%s auth_method=%s status=%d duration_ms=%d",
                method, path, client_ip, auth_method, status_code, duration_ms
            )

        return response
