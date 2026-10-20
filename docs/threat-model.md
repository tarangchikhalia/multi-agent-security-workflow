# Threat Model

Here is the list of all considered threats and the mitigation plan for each. This is not a complete list

## Critical (P0)

| # | Threat | Main mitigations |
| --- | --- | --- |
| T1 | Confused deputy | No standing resource credentials, only exchanged tokens |
| T2 | Prompt injection | Resource-side authorization, least-privilege scopes, tool output treated as untrusted, approval gate |
| T3 | Routing manipulation | Allowlist, state preconditions, hop and budget limits, router output treated as untrusted |
| T4 | Scope escalation at handoff | Scope ceilings, intersection with user cap, re-exchange per hop, no token forwarding |
| T5 | DB bypass (shared credential, psql CLI) | Per-user roles or RLS, no superuser credentials in agent environments |
| T6 | Delete via alternate path | No delete tools, DB roles without DELETE or DDL, REST rejects delete for agent tokens |

## High (P1)

| # | Threat | Main mitigations |
| --- | --- | --- |
| T7 | Object-level bypass (Junior 2) | Ownership check on every write |
| T8 | Token leakage | Tokens in tool context only, log redaction, short TTL |
| T9 | Malicious skill | Skill allowlist, sandboxing, egress limits, per-invocation narrowed token |
| T10 | Session contamination | Per-user session isolation, no cross-user memory |
| T11 | Over-privileged manifest | Security review of every manifest and scope change, scope lint against declared tools, no delete scope ever mapped, periodic recertification |
| T12 | Shared-library supply chain | Pinned and hash-locked versions, internal registry, security review on platform/libs, conformance suite as a mandatory CI gate, SBOM per deployable |


## Medium (P2)

| # | Threat | Main mitigations |
| --- | --- | --- |
| T13 | Token replay or misuse | Audience restriction, short TTL, optional sender-constrained tokens |
| T14 | Rogue, impersonated, or compromised agent | Confidential clients, exchange permitted only for the orchestrator, ceilings enforced in Keycloak, network segmentation, no audit volume in agent containers, agent output treated as untrusted |
| T15 | Stale permissions | Short TTL, no refresh tokens held by agents, re-exchange per hop |
| T16 | Repudiation | Correlation ID, user plus actor on every event, hash-chained logs |

Each threat model is planned to be documented in detail.