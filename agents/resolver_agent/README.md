# Resolver agent

Independent Google ADK + LiteLLM/OpenAI repair agent. Exposes `GET /health`
and `POST /invoke`; `contract.json` matches Support and Debug.

Start resources, then the optional agent:

```sh
docker compose up -d --build --wait
docker compose --profile agents up -d --build resolver_agent
curl http://127.0.0.1:8012/invoke -H 'Content-Type: application/json' \
  -d '{"task":"Repair advanced reports for acme; verify applied configuration"}'
```

Set `OPENAI_API_KEY` and `OPENAI_MODEL` in `.env`. Compose supplies the four
resource URLs and bearer tokens; no database credentials are provided.
`RESOLVER_AGENT_PORT` defaults to 8012.

Tools explicitly allow Docs and Requests reads/writes, Service MCP reads,
feature updates and reloads, and direct Service API GET/PATCH/POST operations.
Deletion is excluded. Feature updates change desired state; reload applies it.
Each invocation gets fresh history, at most 12 model calls and 180 seconds;
resource calls have a 15-second limit. Writes are not automatically retried.
Failures return partial findings and diagnostic traces; verify resource state
before retrying because writes may have applied before a timeout.

This local baseline has unauthenticated agent endpoints, standing resource
credentials, and no peer handoffs or identity enforcement. Manifests are
descriptive; traces are not a trusted audit trail.

Offline validation: `.venv/bin/pytest agents/resolver_agent -q` from the repo root.
