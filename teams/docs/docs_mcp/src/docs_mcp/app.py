"""Synthetic documentation resource. Ownership is metadata in this baseline."""

from typing import Annotated, Any
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
Limit = Annotated[int, Field(ge=1, le=100)]


def create_app() -> ASGIApp:
    mcp = FastMCP(
        "Documentation",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*", "docs_tool:8000"],
            allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"],
        ),
    )

    @mcp.tool()
    def list_documents(
        search: Annotated[str, Field(max_length=200)] = "", limit: Limit = 50
    ) -> list[dict[str, Any]]:
        """Find documents by title/body substring; an empty search lists all."""
        with connect() as db:
            return db.execute(
                "SELECT * FROM docs.documents "
                "WHERE strpos(lower(title || ' ' || body), lower(%s)) > 0 "
                "ORDER BY id LIMIT %s",
                (search, limit),
            ).fetchall()

    @mcp.tool()
    def get_document(document_id: Key) -> dict[str, Any]:
        """Read one document, including its owner and last modification time."""
        with connect() as db:
            row = db.execute(
                "SELECT * FROM docs.documents WHERE id = %s", (document_id,)
            ).fetchone()
            if row is None:
                raise ToolError("not_found: document")
            return row

    @mcp.tool()
    def create_document(title: Title, body: Body, owner: Key) -> dict[str, Any]:
        """Create a document. Owner is metadata, not a caller identity claim."""
        with connect() as db:
            row = db.execute(
                "INSERT INTO docs.documents (id, title, body, owner) VALUES (%s, %s, %s, %s) "
                "RETURNING *",
                (str(uuid4()), title, body, owner),
            ).fetchone()
            assert row is not None
            return row

    @mcp.tool()
    def update_document(
        document_id: Key, title: Title | None = None, body: Body | None = None
    ) -> dict[str, Any]:
        """Change title and/or body of an existing document without changing ownership."""
        if title is None and body is None:
            raise ToolError("invalid_input: provide title or body")
        with connect() as db:
            row = db.execute(
                "UPDATE docs.documents SET title = COALESCE(%s, title), "
                "body = COALESCE(%s, body), updated_at = clock_timestamp() "
                "WHERE id = %s RETURNING *",
                (title, body, document_id),
            ).fetchone()
            if row is None:
                raise ToolError("not_found: document")
            return row

    @mcp.tool()
    def delete_document(document_id: Key) -> dict[str, Any]:
        """Permanently delete a document. Linked ticket IDs remain historical references."""
        with connect() as db:
            row = db.execute(
                "DELETE FROM docs.documents WHERE id = %s RETURNING id", (document_id,)
            ).fetchone()
            if row is None:
                raise ToolError("not_found: document")
            return {"id": row["id"], "deleted": True}

    app = mcp.streamable_http_app()

    async def health(request: Request) -> JSONResponse:
        # This check is deliberately unauthenticated and discloses no configuration.
        ready = await run_in_threadpool(check_database)
        return JSONResponse(
            {"status": "ok" if ready else "unavailable"}, status_code=200 if ready else 503
        )

    app.add_route("/health", health, methods=["GET"])
    return BearerAuth(app)
