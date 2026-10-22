# Documentation agent

Independent Python skill runner using OpenAI Responses, with a packaged `SKILL.md`
and four typed Docs tools: list, get, create, and update. No shell execution or deletion.
It exposes `GET /health` and `POST /invoke` using the same versioned contract as the
Support, Debug, and Resolver agents.

Set `OPENAI_API_KEY` and `OPENAI_MODEL` in `.env`, start the resources, then:

```sh
docker compose --profile agents up --build -d --wait documentation_agent
curl http://127.0.0.1:8013/invoke -H 'Content-Type: application/json' \
  -d '{"task":"Read doc-feature-guide, add configuration reload instructions, and verify the saved guide."}'
```

`DOCUMENTATION_AGENT_PORT` defaults to 8013. Compose supplies only `DOCS_MCP_URL`
and `DOCS_TOKEN`; no Requests, Service, or database credentials are supplied.
`OPENAI_MODEL` accepts the same model value as the other agents, including an optional
`openai/` prefix.

The runner uses fresh local history, disables Responses storage and SDK retries,
and permits at most 12 model turns, 12 tool calls per turn, and 180 seconds per invocation.
Docs calls have a 15-second limit. Tool arguments are validated before each batch;
tool failures stop execution and return partial findings. Writes are never automatically
retried: check saved state before retrying after any failure or timeout.

Endpoints are unauthenticated in this local baseline. Standing credentials remain in
transport context. The manifest is descriptive, and diagnostic traces are not a trusted
audit trail. Peer handoffs are deferred, as in the other current agent packages.

Offline tests use the real OpenAI SDK over scripted HTTP and require no API key:

```sh
.venv/bin/pytest agents/documentation_agent -q
# Requires the running lab; resets synthetic data via the clean_lab fixture:
.venv/bin/pytest agents/documentation_agent --integration -q
```
