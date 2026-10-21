# Support request agent

Independent Python 3.14 Google ADK agent using LiteLLM to call OpenAI. Reads Docs,
reads/writes Requests, and has no database credentials, backend access, deletion tools,
or peer handoffs. The other agents in `docs/plans/agents.md` remain future work.

From the repository root, add `OPENAI_API_KEY` and `OPENAI_MODEL` to `.env`.
Use an OpenAI model ID, with or without the `openai/` prefix. Both values are required;
startup fails if either is blank. Compose passes only the two resource tokens and
model settings to this container; `.env` is excluded from the image.

```sh
docker compose --profile agents up --build -d --wait support_agent
curl --fail http://127.0.0.1:8010/health
curl --fail http://127.0.0.1:8010/invoke \
  -H 'Content-Type: application/json' \
  -d '{"task":"Read ticket-acme and its linked guide. Summarize the issue without changing anything."}'
```

If the lab has no fixtures, explicitly seed them with `uv run python -m scripts.fixtures seed`.
Agent startup never seeds or resets data. `SUPPORT_AGENT_PORT` overrides the default 8010.
Resource-only Compose startup continues to work without OpenAI configuration.

`GET /health` is a process/configuration check, not a model or resource readiness probe.
`POST /invoke` accepts `version` ("1"), `task`, optional `context`, `run_id`,
`max_model_calls` (1–12), and `timeout_seconds` (1–180). See `contract.json` for schemas.
It returns `status`, `summary`, partial `findings`, sanitized `errors`, and tool-name/status
`trace` entries. A failed execution returns HTTP 200 with `status: failed`; invalid input is
HTTP 422. Clients must check `status`. There are no automatic write retries; a timeout
can occur after a write commits, so inspect the resource before retrying.

Each invocation uses a fresh in-memory runner and session. Resource calls have a total
15-second limit. The diagnostic trace is not a trusted audit trail. Tool arguments and
credentials are not included in it. This local baseline has unauthenticated agent endpoints
and standing resource tokens; keep it on localhost with synthetic data. Instructions to
treat resource text as untrusted do not implement the planned identity or policy controls.

```sh
uv run pytest agents/support_agent/tests -q
# Read-only scripted-model checks against running resource HTTP endpoints:
uv run pytest agents/support_agent/tests/test_resources.py --integration -q
```

Offline tests use scripted model responses with the real ADK runner. The integration
check uses actual MCP resources without changing fixtures. A live call to `/invoke`
uses the configured OpenAI account. To stop only the agent:
`docker compose --profile agents stop support_agent`.
