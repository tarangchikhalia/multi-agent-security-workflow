import asyncio
import subprocess
import sys

import httpx
import pytest

from scripts.client import ROOT, authorization, call, service_url, session
from scripts.walkthrough import run

pytestmark = pytest.mark.integration


def fixtures(action):
    subprocess.run(
        [sys.executable, "-m", "scripts.fixtures", action],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_complete_walkthrough_including_deletes(clean_lab):
    asyncio.run(run(deletes=True))


def test_seed_preserves_edits_and_reset_restores_fixtures(clean_lab):
    async def scenario():
        async with session("docs") as docs, session("service_mcp") as db:
            await call(docs, "update_document", document_id="doc-feature-guide", title="Edited")
            await call(
                db, "update_feature", tenant_id="acme", feature_key="advanced_reports", enabled=True
            )
            await call(docs, "delete_document", document_id="doc-disposable")
            await call(db, "delete_configuration", tenant_id="acme", feature_key="notifications")
            fixtures("seed")
            assert (await docs.call_tool("get_document", {"document_id": "doc-disposable"})).isError
            applied = await call(db, "get_configuration", tenant_id="acme")
            assert all(row["feature_key"] != "notifications" for row in applied["features"])
            assert (await call(docs, "get_document", document_id="doc-feature-guide"))[
                "title"
            ] == "Edited"
            features = await call(db, "get_features", tenant_id="acme")
            assert next(row for row in features if row["feature_key"] == "advanced_reports")[
                "enabled"
            ]
            assert len(await call(docs, "list_documents")) == 2
            fixtures("reset")
            assert (await call(docs, "get_document", document_id="doc-disposable"))[
                "id"
            ] == "doc-disposable"
            applied = await call(db, "get_configuration", tenant_id="acme")
            assert any(row["feature_key"] == "notifications" for row in applied["features"])
            assert (await call(docs, "get_document", document_id="doc-feature-guide"))[
                "title"
            ] == "Troubleshoot tenant features"
            features = await call(db, "get_features", tenant_id="acme")
            assert not next(row for row in features if row["feature_key"] == "advanced_reports")[
                "enabled"
            ]

    asyncio.run(scenario())


def test_resource_credentials_are_not_interchangeable(clean_lab):
    for service in ["docs", "requests", "service_mcp", "service_api"]:
        other = "docs" if service != "docs" else "service_api"
        path = (
            "/tenants/acme/configuration/advanced_reports" if service == "service_api" else "/mcp"
        )
        response = httpx.request(
            "DELETE" if service == "service_api" else "POST",
            service_url(service) + path,
            headers=authorization(other),
        )
        assert response.status_code == 401


def test_state_survives_container_recreation(clean_lab):
    async def change():
        async with (
            session("docs") as docs,
            session("requests") as requests,
            session("service_mcp") as db,
        ):
            await call(docs, "delete_document", document_id="doc-disposable")
            await call(requests, "append_note", request_id="ticket-acme", body="Persistent note")
            await call(
                db, "update_feature", tenant_id="acme", feature_key="advanced_reports", enabled=True
            )

    asyncio.run(change())
    with httpx.Client(
        base_url=service_url("service_api"), headers=authorization("service_api")
    ) as api:
        assert api.delete("/tenants/acme/configuration/notifications").status_code == 204
    subprocess.run(
        ["docker", "compose", "up", "-d", "--force-recreate", "--wait"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
    )

    async def verify():
        async with (
            session("docs") as docs,
            session("requests") as requests,
            session("service_mcp") as db,
        ):
            assert (await docs.call_tool("get_document", {"document_id": "doc-disposable"})).isError
            assert (await call(requests, "get_request", request_id="ticket-acme"))["notes"][0][
                "body"
            ] == "Persistent note"
            features = await call(db, "get_features", tenant_id="acme")
            assert next(row for row in features if row["feature_key"] == "advanced_reports")[
                "enabled"
            ]

    asyncio.run(verify())
    with httpx.Client(
        base_url=service_url("service_api"), headers=authorization("service_api")
    ) as api:
        assert [
            row["feature_key"] for row in api.get("/tenants/acme/configuration").json()["features"]
        ] == ["advanced_reports"]
