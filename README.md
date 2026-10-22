# Multi-Agent security workflow

This is a proof of concept demo project for teams developing and orchestrating multi-agent workflows.

It shows how to build a multi-agent workflow securely and how to pass user permissions to agents when they call
protected external resources and hand work to each other.

## Goal

We simulate a multi-agent support workflow with multiple users and resources. The learning outcomes are:
- Teams understand why designing secure agents matters.
- Teams see how a bad actor can exploit a multi-agent environment.

We analyze mutiple threats with an exploit demo, and how to secure the exploitation with mitigation plan and tests

For every workflow, team should be able to explain who acted, with whose permission and what resource.

## Scope

We define the scope, permission model and the workflow for this PoC demo. See scope here -[Scope](./docs/scope.md)

## Architecture

See architecture here - [Architecture](./docs/architecture.md)

## Threat model

See threat model here - [Threat Model](./docs/threat-model.md)

## Implementation details

See implementation details here - [Implementation details](./docs/implementation.md)

## Run the resource foundation

The four resources are implemented with Docker Compose and synthetic tenant data.
See [setup, interfaces, walkthroughs, and tests](./docs/resources.md) and the
[implementation plan](./docs/plans/resource.md). Static credentials are the current baseline;
identity enforcement and human approval are later milestones.

```sh
cp .env.example .env
uv sync --frozen
docker compose up --build -d --wait
uv run python -m scripts.fixtures seed
uv run python -m scripts.walkthrough --deletes
```

## Run the Support agent

Set `OPENAI_API_KEY` and `OPENAI_MODEL` in `.env`, then run
`docker compose --profile agents up --build -d --wait support_agent`.
The Google ADK + LiteLLM agent listens at `http://127.0.0.1:8010`.
See the [Support agent runbook](agents/support_agent/README.md) for invocation and limits.

The [Debug agent](agents/debug_agent/README.md) reads tickets, guides, and desired/applied
service settings. Start it with
`docker compose --profile agents up --build -d --wait debug_agent`; it listens at
`http://127.0.0.1:8011` and uses the same model settings from `.env`.

The [Documentation agent](agents/documentation_agent/README.md) uses a Python skill
runner and OpenAI Responses to edit Docs through typed tools. Start it with
`docker compose --profile agents up --build -d --wait documentation_agent`; it listens
at `http://127.0.0.1:8013` with the same model settings and Docs credentials only.
