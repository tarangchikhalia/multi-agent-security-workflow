# Service Mcp

Independent backend-team deployable. See [the resource runbook](../../../docs/resources.md).

ASGI factory: `service_mcp.app:create_app`; Compose service: `service_mcp`.

Requires `SERVICE_API_URL`, `SERVICE_API_TOKEN`, and caller-facing `SERVICE_TOKEN`. No database credentials or database driver.
