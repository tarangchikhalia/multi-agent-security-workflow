"""Run deterministic resource workflows through real MCP and HTTP clients."""

import argparse
import asyncio
import logging
from contextlib import AsyncExitStack

import httpx

from scripts.client import authorization, call, service_url, session


def enabled(configuration: dict, key: str) -> bool:
    return next(
        (row["enabled"] for row in configuration["features"] if row["feature_key"] == key), False
    )


async def run(*, deletes: bool = False) -> None:
    async with AsyncExitStack() as stack:
        docs = await stack.enter_async_context(session("docs"))
        requests = await stack.enter_async_context(session("requests"))
        db = await stack.enter_async_context(session("service_mcp"))
        backend = await stack.enter_async_context(
            httpx.AsyncClient(
                base_url=service_url("service_api"),
                headers=authorization("service_api"),
                timeout=15,
            )
        )
        path = "/tenants/acme/configuration"
        before = (await backend.get(path)).raise_for_status().json()
        control = (await backend.get("/tenants/globex/configuration")).raise_for_status().json()
        if enabled(before, "advanced_reports"):
            raise RuntimeError(
                "Walkthrough requires broken fixtures. Run scripts.fixtures reset first."
            )

        ticket = await call(requests, "get_request", request_id="ticket-acme")
        document = await call(docs, "get_document", document_id=ticket["document_ids"][0])
        desired = await call(db, "get_features", tenant_id="acme")
        assert (
            next(row for row in desired if row["feature_key"] == "advanced_reports")["enabled"]
            is False
        )
        print("Inspected Acme's ticket, troubleshooting document, and desired/applied settings.")
        await call(
            db, "update_feature", tenant_id="acme", feature_key="advanced_reports", enabled=True
        )
        assert not enabled((await backend.get(path)).raise_for_status().json(), "advanced_reports")
        applied = await call(db, "reload_configuration", tenant_id="acme")
        assert (await backend.get(path)).raise_for_status().json() == applied
        assert enabled(applied, "advanced_reports")
        await call(
            docs,
            "update_document",
            document_id=document["id"],
            body=document["body"] + "\nVerified Acme advanced reports after reload.",
        )
        await call(
            requests,
            "append_note",
            request_id="ticket-acme",
            body="Enabled desired advanced_reports, reloaded backend, verified recovery.",
        )
        closed = await call(requests, "update_request", request_id="ticket-acme", status="closed")
        assert closed["status"] == "closed"
        assert (
            await backend.get("/tenants/globex/configuration")
        ).raise_for_status().json() == control
        print("Fixed desired settings, verified runtime after reload, and closed the ticket.")

        if deletes:
            await call(db, "delete_configuration", tenant_id="acme", feature_key="advanced_reports")
            deleted = (await backend.get(path)).raise_for_status().json()
            assert not enabled(deleted, "advanced_reports")
            desired = await call(db, "get_features", tenant_id="acme")
            assert next(row for row in desired if row["feature_key"] == "advanced_reports")[
                "enabled"
            ]
            restored = await call(db, "reload_configuration", tenant_id="acme")
            assert enabled(restored, "advanced_reports")
            result = await call(docs, "delete_document", document_id="doc-disposable")
            assert result["deleted"]
            historical = await call(requests, "get_request", request_id="ticket-delete-demo")
            assert "doc-disposable" in historical["document_ids"]
            print("Deleted and restored applied configuration; deleted disposable document.")
            print("Baseline credentials permit deletion. Approval and agent denial come later.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--deletes", action="store_true", help="Also exercise deletion capabilities"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(run(deletes=args.deletes))


if __name__ == "__main__":
    main()
