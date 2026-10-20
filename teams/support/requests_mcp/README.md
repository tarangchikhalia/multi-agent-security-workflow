# requests_mcp

Independent Python 3.14 deployable for the resource lab.

See the [resource runbook](../../../docs/resources.md) for credentials, interfaces and fixtures.
From the repository root:

```sh
docker compose up --build -d --wait
uv run python -m scripts.fixtures seed
uv run pytest teams/support/requests_mcp/tests --integration -q
```

Configuration: `SERVICE_TOKEN`, `DATABASE_URL` (libpq string), and standard `PG*` environment
variables. The container receives only its own resource database credential.
ASGI factory: `requests_mcp.app:create_app`; Compose service: `requests`.
`GET /health` checks database connectivity without requiring a bearer token.
