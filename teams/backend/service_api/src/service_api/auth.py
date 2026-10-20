"""Baseline service credential boundary, replaced by delegated auth in a later phase."""

import hmac
import os

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class BearerAuth:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        token = os.environ.get("SERVICE_TOKEN", "")
        if not token.strip():
            raise RuntimeError("SERVICE_TOKEN must be configured")
        self.expected = f"Bearer {token}".encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] != "/health":
            supplied = Headers(scope=scope).getlist("authorization")
            if len(supplied) != 1 or not hmac.compare_digest(supplied[0].encode(), self.expected):
                response = JSONResponse(
                    {"error": "unauthorized"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
