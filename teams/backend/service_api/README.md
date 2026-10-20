# Service Api

Independent backend-team deployable. See [the resource runbook](../../../docs/resources.md).

ASGI factory: `service_api.app:create_app`; Compose service: `service_api`.

Requires `DATABASE_URL` (or libpq PG variables) and `SERVICE_TOKEN`. Own database: `service_db`.
