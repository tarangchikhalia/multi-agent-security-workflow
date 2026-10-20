import asyncio

import pytest

from scripts.client import call, session

pytestmark = pytest.mark.integration


def test_all_service_operations(clean_lab, service_db):
    async def scenario():
        async with session("service_mcp") as db:
            assert {t.name for t in (await db.list_tools()).tools} == {
                "list_tenants",
                "get_features",
                "update_feature",
                "get_configuration",
                "reload_configuration",
                "delete_configuration",
            }
            assert len(await call(db, "list_tenants")) == 2
            original = await call(db, "get_features", tenant_id="globex")
            changed = await call(
                db, "update_feature", tenant_id="acme", feature_key="advanced_reports", enabled=True
            )
            assert changed["enabled"] is True
            applied = await call(db, "get_configuration", tenant_id="acme")
            assert not next(
                r for r in applied["features"] if r["feature_key"] == "advanced_reports"
            )["enabled"]
            await call(db, "reload_configuration", tenant_id="acme")
            await call(db, "delete_configuration", tenant_id="acme", feature_key="advanced_reports")
            applied = await call(db, "get_configuration", tenant_id="acme")
            assert all(r["feature_key"] != "advanced_reports" for r in applied["features"])
            restored = await call(db, "reload_configuration", tenant_id="acme")
            assert next(r for r in restored["features"] if r["feature_key"] == "advanced_reports")[
                "enabled"
            ]
            assert service_db.execute(
                "SELECT enabled FROM settings.features WHERE tenant_id='acme' "
                "AND feature_key='advanced_reports'"
            ).fetchone() == (True,)
            service_db.execute(
                "UPDATE settings.features SET enabled=false WHERE tenant_id='acme' "
                "AND feature_key='advanced_reports'"
            )
            service_db.commit()
            features = await call(db, "get_features", tenant_id="acme")
            assert (
                next(row for row in features if row["feature_key"] == "advanced_reports")["enabled"]
                is False
            )
            assert await call(db, "get_features", tenant_id="globex") == original
            for args in [
                {"tenant_id": "acme", "feature_key": "missing", "enabled": True},
                {"tenant_id": "acme", "feature_key": "advanced_reports", "enabled": "false"},
            ]:
                assert (await db.call_tool("update_feature", args)).isError
            assert (await db.call_tool("get_features", {"tenant_id": "missing"})).isError

    asyncio.run(scenario())
