# Three databases with Service API and Service MCP

Use one PostgreSQL instance with bootstrap-owned `docs_db`, `requests_db`, and `service_db`.
Docs MCP connects only to docs_db, Requests MCP only to requests_db, Service API only to service_db.
Each has one service role with no DDL privileges or access to other databases.
Requests has its own seeded tenant catalog; document references remain historical IDs.

Service MCP is an independent backend-team package. It wraps Service API exclusively, has a
caller-facing bearer token and a configured API token, and has no database credentials.
Remove the former database MCP, credentials, CI entries, and psql demonstration. Manual psql
connectivity remains available, without a skill, demonstration script, or walkthrough.

| Service API | Service MCP |
| --- | --- |
| GET /tenants | list_tenants |
| GET /tenants/{tenant_id}/features | get_features |
| PATCH /tenants/{tenant_id}/features/{feature_key}, {enabled: boolean} | update_feature |
| GET /tenants/{tenant_id}/configuration | get_configuration |
| POST /tenants/{tenant_id}/configuration/reload | reload_configuration |
| DELETE /tenants/{tenant_id}/configuration/{feature_key} | delete_configuration |

Features are desired settings; configuration is applied state. Both live in service_db.
Reload atomically replaces one tenant's applied settings from desired settings. Deletion removes
only applied state; missing means disabled, and reload restores it from desired state.
Service API owns validation and business rules. MCP translates API errors without database fallback.

Split initialization, seed, and reset by database. Seed preserves edits; explicit reset restores
synthetic fixtures. Use a new Compose volume, preserving the previous volume without migration.
The support walkthrough inspects and updates desired settings through Service MCP, reloads applied
configuration, verifies through Service API, updates the guide, and closes the ticket. Preserve
document deletion and historical ticket references. Static credentials remain the baseline;
identity enforcement, agent permissions, and approval gates come later.

Verify database connection isolation and no DDL with the Python driver, all six MCP operations,
desired/applied transitions, deletion and restoration, tenant isolation, validation, API failures,
Docs and Requests lifecycles, support walkthrough, seed/reset behavior, and container recreation.
Run formatting, lint, type checks, and the complete integration suite. Leave changes uncommitted.
