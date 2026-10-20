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
