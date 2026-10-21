# Debug agent

Independent Python 3.14 Google ADK + LiteLLM/OpenAI diagnostic agent. Reads Docs,
Requests, Service MCP (tenants, desired features, applied configuration), and Service
API (GET applied configuration). It has no database credentials or mutation tools.
Resource credentials still have broader authority in this baseline; tool selection
enforces the agent's read-only behavior. Peer handoffs are not implemented.

Set `OPENAI_API_KEY` and `OPENAI_MODEL` in the repository `.env`, then:

```sh
docker compose --profile agents up --build -d --wait debug_agent
curl --fail http://127.0.0.1:8011/health
curl --fail http://127.0.0.1:8011/invoke \
  -H 'Content-Type: application/json' \
  -d '{"task":"Diagnose ticket-acme using its guide. Compare desired features and applied configuration for Acme. Make no changes."}'
```

`DEBUG_AGENT_PORT` overrides port 8011. Both model variables are required at startup;
an OpenAI model ID may include the `openai/` prefix. Resource-only startup does not
require model configuration. Startup never seeds or resets data.

The invocation contract matches Support (`contract.json`): version "1", required
`task`, optional `context`, `run_id`, `max_model_calls` (1–12), and
`timeout_seconds` (1–180). Responses include completion/failure `status`, `summary`,
partial `findings`, sanitized `errors`, and tool-name/status `trace`. Check `status`
even with HTTP 200. Invalid input is HTTP 422. Each invocation has fresh history
and 15-second resource-call limits. Health checks process/configuration only.

This synthetic local baseline has unauthenticated agent endpoints and standing
resource tokens. Keep it on localhost. Diagnostic traces are not trusted audit
records. Instructions to treat resource text as untrusted are not identity policy.

```sh
uv run pytest agents/debug_agent/tests -q
# Scripted model with real resources; read-only and no fixture reset:
uv run pytest agents/debug_agent/tests/test_resources.py --integration -q
docker compose --profile agents stop debug_agent
```
