# Implementation details

- One deployable per service: orchestrator, each agent, each resource server. Each has its own `pyproject.toml` and Dockerfile.
- Shared libraries are versioned packages that services pin, so an unreviewed library change only reaches a service when it bumps the pin.
- CI is path-filtered: a change under `teams/docs/` builds and tests that deployable plus the conformance suite against it.
- **Network segmentation (Docker Compose for the PoC):** only the orchestrator can reach IdP’s token exchange endpoint, which enforces the sole-exchanger rule at the network level as well as in IdP policy.
- **Audit volume:** writable only by the orchestrator and resource containers. Agent containers do not mount it.
- **Audit signing keys and secrets:** each writing service gets its own HMAC key, and each agent gets only its own client credentials.
- **Contracts between deployables:** orchestrator to agent is a defined request and response (task, summary, narrowed token); agent to resource is MCP or REST with the exchanged token. Nothing else crosses a boundary.

## Vulnerable mode

- One flag (for example `ENFORCEMENT_MODE=strict` or `permissive`) read by the orchestrator and every resource.
- Permissive mode disables checks per demo (allowlist, token scope, ownership, DB role, approval gate, hash chaining), one at a time or together.
- Same code path, same policy engine, only the checks toggled, so the demo proves the fix is real.
- Each threat demo runs three steps: permissive run (exploit succeeds, audit log shows the gap), strict run (same input is blocked, audit log shows why), then a one-line diff naming the control that made the difference.
- Guardrails: isolated environment, synthetic data, strict by default, banner in logs and UI, never deployed anywhere reachable outside the demo.

Deliverables for the teams: an attacker playbook (entry point, pivot, impact per threat) and a short checklist of secure-agent design rules.

## 11. Repository structure and ownership

One monorepo with ownership boundaries and separate deployables. In a real environment each agent is built by the team that owns the matching tool, so the security and platform team owns the trust layer and product teams own their agent and resource.

### Ownership

| Owner | Owns |
| --- | --- |
| Security/platform team | Orchestrator, router policy, token broker, authz library, audit library, Keycloak configuration, handoff allowlist |
| Documentation team | Docs MCP server and Documentation agent |
| Support tooling team | Requests MCP server and Support agent |
| DB/platform team | DB MCP server, Postgres roles and RLS |
| Backend team | Backend REST API |
| SRE or platform team | Debug and Resolver agents, which span all resources |

### Layout

```text
multi-agent-security-workflow/
├── CODEOWNERS                 per-folder owners, enforced in review
├── platform/                  security-owned
│   ├── orchestrator/
│   ├── libs/                  authz, audit, broker (versioned packages)
│   ├── policy/                handoff allowlist, scope ceilings, approval-gate config
│   └── keycloak/              realm export: clients, roles, scope mappings
├── teams/
│   ├── docs/                  docs_mcp/ + agent/ + agent.manifest.yaml
│   ├── support/               requests_mcp/ + agent/ + agent.manifest.yaml
│   ├── db/                    db_mcp/ + postgres init SQL
│   ├── backend/               backend_api/
│   └── sre/                   debug_agent/ + resolver_agent/ + manifests
├── conformance/               shared negative-test suite run in each team’s CI
├── data/seed/                 synthetic docs, requests, tables with owner fields
├── scenarios/                 W1 to W5, attack payloads
├── tests/                     matrix/, threats/ (t01 to t16), workflows/
└── docs/                      planning doc, attacker playbook, design-rules checklist
```

### Rules for multi-team ownership

- **Agent teams request scopes and never grant them.** Each agent ships a manifest (agent ID, runtime, requested scopes, proposed handoff edges). Security reviews it and provisions the Keycloak client.
- **Manifests are requests, not authority.** The authoritative ceiling lives in Keycloak and the central policy, so an agent claiming more scope than provisioned is denied.
- **Resource teams enforce with the shared authz library.** The conformance suite checks scope, audience, ownership, and delete-blocking for every resource.
- **Agents are pluggable.** The orchestrator calls each agent through a defined interface and never imports team code, so ADK and skill-based agents sit side by side.

## Implementation language

This workflow PoC is implemented in Python 3.14. In real scenario, this architecture is language agnostic. The agents can be built in any language as long as the agent-to-orchestrator communication protocol and
schema is decided

## Build order

| Phase | Build | Demo milestone |
| --- | --- | --- |
| Resource | Docs MCP, Requests MCP, DB MCP plus psql path, backend REST API, seed data with owner fields | Resources work as they do today (simple credentials) |
| Agents | The four agents wired directly to resources and to each other | The problems: agents hold standing credentials (T2), no user identity reaches resources, handoffs are uncontrolled, nothing is logged centrally |
| IdP | Shared authz and audit libraries, resource retrofits | Resources validate tokens, scope, ownership, and delete-blocking, and emit audit events |
| Orchestrator | Router, policy engine, token broker, approval gate, hash-chained audit | W1 to W5 run end to end with controls on |
| Hardening and tests | Vulnerable-mode toggles, T1 to T16 exploit and mitigation tests, conformance suite | Full-attacker demo |
| Observability | Langfuse, Prometheus, Grafana | |

