# Scope

We define Users, Agents, Resources, permission model and workflow

## Scope
### Resources

| Resource | Access path |
| --- | --- |
| Documentation tool | MCP server |
| Support request tool | MCP server |
| Postgres database | MCP server and psql CLI |
| Backend service | REST API |

### Agents

| Agent | Docs | Requests | DB | Backend |
| --- | --- | --- | --- | --- |
| Documentation | Read/write | None | None | None |
| Support | Read | Read/write | None | None |
| Debug | Read | Read | Read | Read |
| Resolver | Read/write | Read/write | Read/write | Read/write |

### Users

| User | Docs | Requests | DB | Backend | Delete |
| --- | --- | --- | --- | --- | --- |
| Junior 1 | Read | Read | Read | Read | No |
| Junior 2 | Read, write on owned objects | Read | Read | Read | No |
| Senior | Read/write | Read/write | Read/write | Read/write | No |
| Architect | Read/write | Read/write | Read/write | Read/write | Yes |

## Permission model

**Effective access = agent scope ∩ user cap.** An agent never exceeds what the logged-in user can do, and the user never gains more than the agent’s scope allows.

- Junior 1 using Resolver: read-only everywhere.
- Junior 2 using Support: writes only on requests they own.
- Architect using any agent: still no delete, because the agent ceiling blocks it.
- Senior using Documentation: docs read/write only, no DB or backend access.

**Junior 2 ownership model:** each doc and request has an `owner` (or `created_by`) field. Junior 2 can write only to objects they own. Test data marks a few objects as owned by Junior 2 and the rest by others.

**Database:** per-user DB roles or Row-Level Security instead of a shared credential, so the MCP server and the psql CLI use the same roles and neither can bypass the other. Agent environments hold no superuser credentials and DB roles lack DELETE and DDL privileges.

**Deletes:** not exposed as agent tools. Also blocked in the resource layer (REST rejects delete for agent tokens, DB roles lack the privilege), so the rule holds even if an agent is compromised.

## Workflow

### W1: Primary (debug, resolve, document)

Support reads the ticket and docs, Debug inspects DB and backend, Resolver applies the fix, Documentation updates the doc, Support updates and closes the ticket.

- Junior 1: steps 1 and 2 work (read only); writes are denied.
- Junior 2: steps 1, 2, 4, and 5 work only on owned objects; the Resolver fix is denied (no DB or backend write).
- Senior: all steps succeed, no deletes.
- Architect: same as Senior, because the agent ceiling still blocks deletes.

### W2: Failure and escalation

The Resolver fix is denied, the denial returns to the orchestrator, and the debug findings go to the user for human escalation. Junior 1 gets findings only (cannot write the ticket). Junior 2 gets an escalation note added by Support on an owned request. Shows fail-closed behavior and T15.

### W3: Documentation only

The user asks the Documentation agent to edit a doc. Junior 1 is denied, Junior 2 is allowed only on owned docs, Senior and Architect are allowed. A delete request is denied for everyone, Architect included. Shows T6 and T7.

### W4: Cross-agent attack (poisoned doc)

A doc read in step 1 contains hidden instructions to steer the router to Resolver, or to delete a record. Junior 1 and Junior 2 writes are denied by user cap. For Senior and Architect an in-scope write may succeed, which is the residual risk, and the audit log and approval gate address it. Any delete attempt is denied for everyone. Shows T2, T3, T4, T6.

Run twice with the gate on: first without provenance shown (the owner approves and the attack lands), then with provenance shown (the warning makes the manipulation visible and the owner denies).

### W5: Human approval required

Resolver drafts the fix and the orchestrator pauses. The owner sees the diff, agent chain, correlation ID, provenance, and reasoning, then approves or denies. Only after approval does the write run, and it still passes scope and ownership checks. The decision is logged.
