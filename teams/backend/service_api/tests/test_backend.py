import httpx
import pytest

from scripts.client import authorization, service_url

pytestmark = pytest.mark.integration


def test_delete_and_reload_are_tenant_scoped(clean_lab, service_db):
    with httpx.Client(
        base_url=service_url("service_api"), headers=authorization("service_api")
    ) as api:
        path = "/tenants/acme/configuration"
        control = api.get("/tenants/globex/configuration").raise_for_status().json()
        assert api.delete(f"{path}/advanced_reports").status_code == 204
        deleted = api.get(path).raise_for_status().json()
        assert deleted["missing_feature_enabled"] is False
        assert [row["feature_key"] for row in deleted["features"]] == ["notifications"]
        assert service_db.execute(
            "SELECT count(*) FROM settings.features WHERE tenant_id='acme' "
            "AND feature_key='advanced_reports'"
        ).fetchone() == (1,)
        assert api.delete(f"{path}/advanced_reports").status_code == 404
        restored = api.post(f"{path}/reload").raise_for_status().json()
        assert len(restored["features"]) == 2
        assert api.get("/tenants/globex/configuration").json() == control


def test_unknown_objects_and_invalid_paths(clean_lab):
    with httpx.Client(
        base_url=service_url("service_api"), headers=authorization("service_api")
    ) as api:
        for method, path in [
            ("GET", "/tenants/missing/configuration"),
            ("POST", "/tenants/missing/configuration/reload"),
            ("DELETE", "/tenants/missing/configuration/advanced_reports"),
            ("DELETE", "/tenants/acme/configuration/missing"),
        ]:
            assert api.request(method, path).status_code == 404
        assert api.delete("/tenants/acme/configuration/invalid%20key").status_code == 422


def test_desired_validation_and_no_implicit_reload(clean_lab):
    with httpx.Client(
        base_url=service_url("service_api"), headers=authorization("service_api")
    ) as api:
        path = "/tenants/acme/features/advanced_reports"
        for body in [{}, {"enabled": "false"}, {"enabled": 1}, {"enabled": True, "extra": 1}]:
            assert api.patch(path, json=body).status_code == 422
        for path in [
            "/tenants/missing/features/advanced_reports",
            "/tenants/acme/features/missing",
        ]:
            assert api.patch(path, json={"enabled": True}).status_code == 404
        assert api.get("/tenants?limit=0").status_code == 422
        assert api.get("/tenants?limit=101").status_code == 422
        assert api.get("/tenants/missing/features").status_code == 404
        assert api.patch("/tenants/acme/features/advanced_reports", json={"enabled": True}).json()[
            "enabled"
        ]
        applied = api.get("/tenants/acme/configuration").json()
        assert not next(r for r in applied["features"] if r["feature_key"] == "advanced_reports")[
            "enabled"
        ]
