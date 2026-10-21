"""Synthetic support requests, independent of documentation storage."""

from typing import Annotated, Any, Literal
from uuid import uuid4

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from .auth import BearerAuth
from .storage import check_database, connect

Key = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[\w.-]+$")]
Title = Annotated[str, Field(min_length=1, max_length=200, pattern=r"\S")]
Body = Annotated[str, Field(min_length=1, max_length=100_000, pattern=r"\S")]
Status = Literal["open", "in_progress", "closed"]
Links = Annotated[list[Key], Field(max_length=100)]


def read_ticket(db: Any, request_id: str) -> dict[str, Any]:
    row = db.execute("SELECT * FROM support.requests WHERE id = %s", (request_id,)).fetchone()
    if row is None:
        raise ToolError("not_found: request")
    row["notes"] = db.execute(
        "SELECT id, body, created_at FROM support.notes WHERE request_id = %s "
        "ORDER BY created_at, id",
        (request_id,),
    ).fetchall()
    return row


def create_app() -> ASGIApp:
    mcp = FastMCP(
        "Support requests",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*", "requests_tool:8000"],
            allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"],
        ),
    )

    @mcp.tool()
    def list_requests(
        status: Status | None = None,
        owner: Key | None = None,
        tenant_id: Key | None = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 50,
    ) -> list[dict[str, Any]]:
        """List requests with optional status, owner, and tenant filters."""
        with connect() as db:
            return db.execute(
                "SELECT * FROM support.requests WHERE (%s::text IS NULL OR status = %s) "
                "AND (%s::text IS NULL OR owner = %s) AND (%s::text IS NULL OR tenant_id = %s) "
                "ORDER BY id LIMIT %s",
                (status, status, owner, owner, tenant_id, tenant_id, limit),
            ).fetchall()

    @mcp.tool()
    def get_request(request_id: Key) -> dict[str, Any]:
        """Read a ticket and its notes. Document links are historical IDs."""
        with connect() as db:
            return read_ticket(db, request_id)

    @mcp.tool()
    def create_request(
        tenant_id: Key,
        title: Title,
        description: Body,
        owner: Key,
        document_ids: Links | None = None,
    ) -> dict[str, Any]:
        """Create an open support request for a known tenant."""
        with connect() as db:
            # A readable tenant catalog makes unknown tenants an explicit input error.
            tenant = db.execute(
                "SELECT id FROM support.tenants WHERE id = %s", (tenant_id,)
            ).fetchone()
            if tenant is None:
                raise ToolError("not_found: tenant")
            request_id = str(uuid4())
            db.execute(
                "INSERT INTO support.requests "
                "(id, tenant_id, title, description, owner, document_ids) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (request_id, tenant_id, title, description, owner, document_ids or []),
            )
            return read_ticket(db, request_id)

    @mcp.tool()
    def update_request(
        request_id: Key,
        title: Title | None = None,
        description: Body | None = None,
        status: Status | None = None,
        document_ids: Links | None = None,
    ) -> dict[str, Any]:
        """Update a ticket without transferring ownership."""
        if all(value is None for value in (title, description, status, document_ids)):
            raise ToolError("invalid_input: provide a field to update")
        with connect() as db:
            row = db.execute(
                "UPDATE support.requests SET title = COALESCE(%s, title), "
                "description = COALESCE(%s, description), status = COALESCE(%s, status), "
                "document_ids = COALESCE(%s, document_ids), updated_at = clock_timestamp() "
                "WHERE id = %s RETURNING id",
                (title, description, status, document_ids, request_id),
            ).fetchone()
            if row is None:
                raise ToolError("not_found: request")
            return read_ticket(db, request_id)

    @mcp.tool()
    def append_note(request_id: Key, body: Body) -> dict[str, Any]:
        """Append a note and return the updated ticket."""
        with connect() as db:
            row = db.execute(
                "UPDATE support.requests SET updated_at = clock_timestamp() "
                "WHERE id = %s RETURNING id",
                (request_id,),
            ).fetchone()
            if row is None:
                raise ToolError("not_found: request")
            db.execute(
                "INSERT INTO support.notes (id, request_id, body) VALUES (%s, %s, %s)",
                (str(uuid4()), request_id, body),
            )
            return read_ticket(db, request_id)

    app = mcp.streamable_http_app()

    async def health(request: Request) -> JSONResponse:
        ready = await run_in_threadpool(check_database)
        return JSONResponse(
            {"status": "ok" if ready else "unavailable"}, status_code=200 if ready else 503
        )

    app.add_route("/health", health, methods=["GET"])
    return BearerAuth(app)
