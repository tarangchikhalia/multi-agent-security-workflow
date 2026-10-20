"""Applied tenant configuration. Missing feature settings mean disabled."""

from typing import Annotated, Any

import psycopg
from fastapi import FastAPI, HTTPException, Path, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StrictBool

from .auth import BearerAuth
from .storage import check_database, connect

Key = Annotated[str, Path(min_length=1, max_length=100, pattern=r"^[\w.-]+$")]


class FeatureUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: StrictBool


def require_tenant(db: Any, tenant_id: str, *, lock: bool = False) -> None:
    # Serialize reload/delete per tenant, including the empty-configuration case.
    query = "SELECT id FROM settings.tenants WHERE id = %s"
    if lock:
        db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (tenant_id,))
    if db.execute(query, (tenant_id,)).fetchone() is None:
        raise HTTPException(404, "tenant not found")


def configuration(db: Any, tenant_id: str) -> dict[str, Any]:
    rows = db.execute(
        "SELECT feature_key, enabled, updated_at FROM runtime.features "
        "WHERE tenant_id = %s ORDER BY feature_key",
        (tenant_id,),
    ).fetchall()
    return {"tenant_id": tenant_id, "missing_feature_enabled": False, "features": rows}


def create_app() -> FastAPI:
    app = FastAPI(title="Service API", version="0.1.0")
    app.add_middleware(BearerAuth)

    @app.exception_handler(psycopg.Error)
    async def database_error(request: Any, error: psycopg.Error) -> JSONResponse:
        # Keep database internals out of the public response.
        return JSONResponse({"error": "database_unavailable"}, status_code=503)

    @app.get("/health", include_in_schema=False)
    def health() -> JSONResponse:
        ready = check_database()
        return JSONResponse(
            {"status": "ok" if ready else "unavailable"}, status_code=200 if ready else 503
        )

    @app.get("/tenants")
    def list_tenants(limit: Annotated[int, Query(ge=1, le=100)] = 50) -> list[dict[str, Any]]:
        with connect() as db:
            return db.execute(
                "SELECT * FROM settings.tenants ORDER BY id LIMIT %s", (limit,)
            ).fetchall()

    @app.get("/tenants/{tenant_id}/features")
    def get_features(tenant_id: Key) -> list[dict[str, Any]]:
        with connect() as db:
            require_tenant(db, tenant_id)
            return db.execute(
                "SELECT * FROM settings.features WHERE tenant_id = %s ORDER BY feature_key",
                (tenant_id,),
            ).fetchall()

    @app.patch("/tenants/{tenant_id}/features/{feature_key}")
    def update_feature(tenant_id: Key, feature_key: Key, body: FeatureUpdate) -> dict[str, Any]:
        with connect() as db:
            require_tenant(db, tenant_id, lock=True)
            row = db.execute(
                "UPDATE settings.features SET enabled = %s, updated_at = clock_timestamp() "
                "WHERE tenant_id = %s AND feature_key = %s RETURNING *",
                (body.enabled, tenant_id, feature_key),
            ).fetchone()
            if row is None:
                raise HTTPException(404, "feature not found")
            return row

    @app.get("/tenants/{tenant_id}/configuration")
    def get_configuration(tenant_id: Key) -> dict[str, Any]:
        with connect() as db:
            require_tenant(db, tenant_id)
            return configuration(db, tenant_id)

    @app.post("/tenants/{tenant_id}/configuration/reload")
    def reload_configuration(tenant_id: Key) -> dict[str, Any]:
        with connect() as db:
            require_tenant(db, tenant_id, lock=True)
            db.execute("DELETE FROM runtime.features WHERE tenant_id = %s", (tenant_id,))
            db.execute(
                "INSERT INTO runtime.features (tenant_id, feature_key, enabled) "
                "SELECT tenant_id, feature_key, enabled FROM settings.features "
                "WHERE tenant_id = %s",
                (tenant_id,),
            )
            return configuration(db, tenant_id)

    @app.delete("/tenants/{tenant_id}/configuration/{feature_key}", status_code=204)
    def delete_configuration(tenant_id: Key, feature_key: Key) -> Response:
        with connect() as db:
            require_tenant(db, tenant_id, lock=True)
            row = db.execute(
                "DELETE FROM runtime.features WHERE tenant_id = %s AND feature_key = %s "
                "RETURNING feature_key",
                (tenant_id, feature_key),
            ).fetchone()
            if row is None:
                raise HTTPException(404, "applied feature not found")
        return Response(status_code=204)

    return app
