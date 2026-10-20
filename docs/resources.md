# Running the resource lab

This milestone implements the resources in [the plan](plans/resource.md). It is a local,
production-inspired security lab. Static service credentials authorize every exposed operation,
including deletion. User caps, ownership enforcement, agent restrictions, approval and centralized
audit are later milestones. Owner fields are metadata today.

## Start

Requirements: Docker with Compose and uv. The project selects Python 3.14; uv can install it.

```sh
cp .env.example .env
uv sync --frozen
docker compose up --build -d --wait
uv run python -m scripts.fixtures seed
uv run python -m scripts.walkthrough --deletes
```

The walkthrough fixes Acme's advanced reports, verifies Globex is untouched, updates the guide and
closes the ticket. With `--deletes` it also deletes/restores an applied feature and permanently deletes
the disposable document. It checks the actual MCP and REST responses; it needs no LLM.

To run it again, restore fixtures explicitly:

```sh
uv run python -m scripts.fixtures reset
uv run python -m scripts.walkthrough --deletes
```

`seed` initializes fixtures once per database; repeat seeds preserve updates and deletions. `reset` truncates all resource data and
restores the fixture set, including any deleted fixtures. Neither runs automatically at service startup.
Do not run reset or integration tests while using the lab interactively. Test runs are serial.
`data/seed/users.json` records identities for the later IdP phase; it does not provision accounts now.

## Services and credentials

| Service | Host URL | Credential in .env | Database role |
| --- | --- | --- | --- |
| Docs MCP | http://127.0.0.1:8001/mcp | DOCS_TOKEN | docs_resource |
| Requests MCP | http://127.0.0.1:8002/mcp | REQUESTS_TOKEN | requests_resource |
| Service MCP | http://127.0.0.1:8003/mcp | SERVICE_MCP_TOKEN | none (HTTP only) |
| Service API | http://127.0.0.1:8004 | SERVICE_API_TOKEN | service_resource |
| PostgreSQL | 127.0.0.1:55432 | *_DB_PASSWORD | Per resource |

Every HTTP call except `GET /health` needs `Authorization: Bearer <service token>`.
Health includes a database connectivity check (Service MCP checks Service API instead) and returns 503 when unavailable. Backend OpenAPI is
available at `/openapi.json` with the bearer header. Ports are configurable through `.env`.
Each database-backed service receives only its own DB password; the bootstrap administrator exists only in Postgres.
Database/schema setup runs only on an empty volume. Editing password values in `.env` does not rotate
an existing role's password. For a disposable lab, recreate the volume after credential/schema changes.

Run a service outside Docker using its independent package:

```sh
# Set DATABASE_URL to a libpq connection string, or use PGHOST/PGPORT/PGUSER/PGPASSWORD.
# SERVICE_TOKEN is required; do not place real secrets in shell history.
uv run --project teams/docs/docs_mcp uvicorn docs_mcp.app:create_app --factory --port 8001
```

The other ASGI factories are `requests_mcp.app:create_app`, `service_mcp.app:create_app`, and
`service_api.app:create_app`. Supply `DATABASE_URL=dbname=<application_db>` when using PG* variables.
Services never import another team's code. Auth and transaction adapters are deliberately local to
these independent packages; versioned shared authz/audit libraries are deferred to the identity phase.

## Operations

| Resource | Tools or routes |
| --- | --- |
| Docs MCP | `list_documents(search, limit)`, `get_document(document_id)`, `create_document(title, body, owner)`, `update_document(document_id, title?, body?)`, `delete_document(document_id)` |
| Requests MCP | `list_requests(status?, owner?, tenant_id?, limit)`, `get_request(request_id)`, `create_request(tenant_id, title, description, owner, document_ids?)`, `update_request(request_id, title?, description?, status?, document_ids?)`, `append_note(request_id, body)` |
| Service MCP | `list_tenants(limit)`, `get_features(tenant_id)`, `update_feature(tenant_id, feature_key, enabled)`, `get_configuration(tenant_id)`, `reload_configuration(tenant_id)`, `delete_configuration(tenant_id, feature_key)` |
| Service API | `GET /tenants`, `GET /tenants/{tenant_id}/features`, `PATCH /tenants/{tenant_id}/features/{feature_key}`, `GET /tenants/{tenant_id}/configuration`, `POST /tenants/{tenant_id}/configuration/reload`, `DELETE /tenants/{tenant_id}/configuration/{feature_key}` |

MCP uses stateless Streamable HTTP and typed tool schemas. List tools default to at most 50 rows,
with a maximum of 100. Search is a literal case-insensitive substring. Updates never create objects
and cannot transfer ownership. Ticket statuses are `open`, `in_progress`, and `closed`.
MCP input/not-found failures return `isError`; unknown REST objects return 404 and invalid paths 422.

Backend desired settings live in `settings.features`; applied state lives in `runtime.features`.
Reload atomically replaces a tenant's applied state from desired state. A configuration response includes
`missing_feature_enabled: false`: absence means disabled. DELETE affects only the named applied setting,
returns 204, and returns 404 if repeated. Reload restores it if desired configuration still contains it.
Reload and deletion serialize per tenant. Other tenants are unaffected.

Document deletion is permanent and returns `{ "id": "...", "deleted": true }`. Ticket document IDs
are historical references and remain even when their target document is deleted. There is no ticket
deletion operation and no arbitrary SQL MCP tool.

In the later secured demo, agent tokens will be denied both delete operations. A document owner can
approve deletion, then an authenticated Architect human executes it through a separate human path.
Approval binds the document and content version; changed content requires new approval. This milestone
provides resource capability only and does not implement that gate or authenticate human approvers.

## Database boundaries and transition

One PostgreSQL instance contains `docs_db`, `requests_db`, and `service_db`.
Each bootstrap-owned database grants CONNECT only to its service role. Roles cannot create
schemas or tables. Requests validates tenants against its own seeded catalog in `support.tenants`.
Document IDs remain historical references, including after document deletion.

Service MCP holds only its caller token and the configured Service API token and URL.
It has no database credentials; API failures become explicit tool errors without fallback.
Manual psql connections remain available to all three databases, but this milestone has no
psql skill, demonstration scripts, or walkthrough.

Compose uses the new `resource-three-db-data` volume. The old `resource-data` volume is
preserved without migration or automatic deletion. Initialization runs only on an empty new
volume. Seed and reset execute separately in each database; reset is not atomic across databases.

## Verification and teardown

```sh
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest                         # offline credential/readiness checks
uv run pytest --integration           # includes all checks; resets synthetic data repeatedly
uv run python -m scripts.fixtures reset
```

Each service's integration tests live alongside its package. `tests/` exercises credential isolation,
the walkthrough, fixture behavior, database privileges, and state surviving recreation of every container. CI selects
image smoke builds by changed deployable and runs the complete Compose integration suite for resource
changes. Lockfiles are committed independently for each deployable and the root test environment.

```sh
docker compose down                   # retain data
docker compose down -v                # explicitly discard all lab data
```

This stack publishes localhost ports only; it has no TLS, delegated identity, backups, or production
operations controls. Keep the synthetic credentials/data local.
