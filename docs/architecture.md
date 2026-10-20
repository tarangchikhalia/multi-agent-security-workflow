# Architecture

We implement an orchestrator pattern. All agent-to-agent handoffs go through a central orchestrator

- **Sole token exchanger:** only the orchestrator calls external identity provider (Okta, Keycloak) for token exchange. Agents hold no exchange rights.
- **Holds the user token:** agents receive only a narrowed, audience-restricted token for their own call.
- **Context passing:** agents return findings to the orchestrator, which forwards a summary (never a token) to the next agent.
- **Central audit:** stamps a correlation ID on every hop.

## Dynamic routing within an allowlist

The LLM proposes the next agent and a reason. Deterministic policy code validates the proposal before any token is minted.

| From | Allowed next |
| --- | --- |
| Support | Debug, Documentation |
| Debug | Resolver, Support |
| Resolver | Debug (verify fix), Documentation, Support |
| Documentation | Support |

Denied by design: Support to Resolver (must debug first), Documentation to Resolver or Debug, and any hop not in the table.

**Checks on every hop**

- The edge exists in the allowlist.
- State precondition: Resolver is reachable only after Debug produced findings in this run.
- Permission pre-check: if user cap ∩ agent ceiling cannot cover the intended action, deny before the call.
- Limits: maximum hop count, cycle detection, per-run budget.
- Optional human approval gate.

## Token flow

1. The user logs in through the orchestrator client (authorization code with PKCE).
2. For each agent call, the orchestrator performs a token exchange with a requested audience and scope.
3. At every handoff, a new token is minted with scope no wider than the user’s cap and the next agent’s ceiling. Scope can only shrink or stay the same.
4. Each resource validates signature, audience, scope, and object-level ownership on every call.

Pass context, not tokens. Tokens stay in session or tool context and never enter prompts or logs.

## Agent runtimes

Agents can be ADK agents or skill-based agents. Security does not depend on the framework: resources enforce, a shared token-broker library wraps the exchange, and each runtime gets a thin adapter. 
Skill scripts receive a short-lived, narrowed token per invocation, never a long-lived credential.

## Human approval

The following controls are the secured target, not the static-credential resource baseline.
Document deletion uses owner approval followed by separate execution by an authenticated Architect
human. Agent tokens cannot delete, even with approval. Execution must match the approved document
and content version; changed content requires new approval.

Configurable, so teams can see the control on and off.

- **Mode:** off, always, or conditional.
- **Conditional triggers (any combination):** target resource (DB, backend), high-risk objects, workflow touched content flagged untrusted, user tier, routing anomaly.
- **Default approver:** the owner of the resource. For docs and requests this is the existing `owner` field; for DB and backend, a configured owner per table or service.
- **Self-approval:** allowed when the requester is the owner.
- **Fail closed:** if the owner is unavailable or the timeout is reached, the write is denied. A resource with no owner on record is also denied.
- **Binding:** approval covers one hashed diff, is single-use, and expires quickly. The approver authenticates separately.
- **Approval never widens permissions.** The write still passes token scope and ownership checks.
- **Provenance display:** because self-approval is allowed, the approval screen shows what triggered the proposed write, names the source doc or request, and flags content the user did not author. A human gate only works if the human has the context to judge.

## Audit trail

For PoC, the audit trail is a local directory in JSON. one file per component, merged by timestamp and correlation ID.

**Fields per event:** correlation ID, `sub`, actor (from `act` or `agent_id`), resource, action and object, decision (allow or deny), reason and deciding layer, mode (strict or permissive), previous and proposed next agent, approval outcome where relevant.

**Rules**

- Resources emit events, since they are the real enforcement point. A token being issued does not mean the action was allowed, so allow or deny is logged explicitly.
- Agents cannot read or write the log directory. File permissions keep a compromised agent from erasing its tracks.
- Never log tokens or secrets. Log claims only.
- Tag permissive-mode runs.

**Tamper evidence**

- Each event stores `prev_hash` and its own `hash` (SHA-256 over the previous hash plus canonical JSON), chained from a genesis value.
- Each hash is signed with an HMAC key held only by the writing component, so someone with file access cannot recompute the chain.
- The orchestrator periodically records each file’s latest hash in a separate anchor file, which catches tail truncation.
- A `verify` command reports the first broken link.


## Resource baseline

One PostgreSQL instance hosts three databases: Docs MCP owns application access to `docs_db`,
Requests MCP to `requests_db`, and Service API to `service_db`. Bootstrap owns all tables;
application roles have only their own database CONNECT and table DML grants, with no DDL.
Requests has a local tenant catalog. Ticket document references are historical IDs.
Service MCP is independently packaged under the backend team, authenticates callers with its
own bearer token, and calls Service API using a separate configured token. It has no DB credentials.
Desired features and applied configuration both live in `service_db`; reload atomically replaces
one tenant's applied state. Deletion affects only applied state; absence means disabled.
