"""Local-only HTTP adapter with invocation-local history and bounded execution."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI
from google.adk.agents import LlmAgent
from google.adk.agents.run_config import RunConfig
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field

from .tools import ResourceTools

logger = logging.getLogger(__name__)


class Invocation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal["1"] = "1"
    task: str = Field(min_length=1, max_length=20_000, pattern=r"\S")
    context: str = Field(default="", max_length=20_000)
    run_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=100)
    max_model_calls: int = Field(default=12, ge=1, le=12)
    timeout_seconds: int = Field(default=180, ge=1, le=180)


class Result(BaseModel):
    version: Literal["1"] = "1"
    run_id: str
    status: Literal["completed", "failed"]
    summary: str
    findings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    trace: list[dict[str, str]] = Field(default_factory=list)


def endpoints() -> dict[str, tuple[str, str]]:
    return {
        "docs": (os.environ["DOCS_MCP_URL"], os.environ["DOCS_TOKEN"]),
        "requests": (os.environ["REQUESTS_MCP_URL"], os.environ["REQUESTS_TOKEN"]),
        "service_mcp": (os.environ["SERVICE_MCP_URL"], os.environ["SERVICE_MCP_TOKEN"]),
        "service_api": (os.environ["SERVICE_API_URL"], os.environ["SERVICE_API_TOKEN"]),
    }


async def execute(request: Invocation) -> Result:
    tools = ResourceTools(endpoints())
    findings: list[str] = []
    summary = ""
    try:
        async with asyncio.timeout(request.timeout_seconds):
            model = os.environ["OPENAI_MODEL"]
            if not model.startswith("openai/"):
                model = f"openai/{model}"
            agent = LlmAgent(
                name="resolver",
                model=LiteLlm(model=model, num_retries=0),
                instruction=Path(__file__).with_name("instructions.md").read_text(),
                tools=tools.exposed(),
            )
            async with InMemoryRunner(agent=agent, app_name="resolver") as runner:
                session = await runner.session_service.create_session(
                    app_name="resolver", user_id="local"
                )
                async for event in runner.run_async(
                    user_id="local",
                    session_id=session.id,
                    new_message=types.Content(
                        role="user",
                        parts=[
                            types.Part(text=f"Task: {request.task}\nContext: {request.context}")
                        ],
                    ),
                    run_config=RunConfig(max_llm_calls=request.max_model_calls),
                ):
                    if event.error_code:
                        raise RuntimeError("model failed")
                    if event.content and event.content.parts:
                        text = "".join(p.text or "" for p in event.content.parts if not p.thought)
                        if text:
                            findings.append(text)
                            if event.is_final_response():
                                summary = text
            if not summary:
                tools.errors.append("Model did not return a final answer")
    except TimeoutError:
        tools.errors.append(
            "Invocation deadline exceeded; writes may already have applied; "
            "verify resource state before retrying"
        )
    except Exception as error:
        # Report categories, never arbitrary SDK messages (which can contain secrets).
        error_type = type(error).__name__
        logger.error(
            "Resolver invocation failed: run_id=%s error_type=%s", request.run_id, error_type
        )
        tools.errors.append(
            f"Agent execution failed ({error_type}); check model and resource configuration"
        )
    return Result(
        run_id=request.run_id,
        status="failed" if tools.errors else "completed",
        summary=summary
        if not tools.errors
        else "Resolver task failed; partial findings are available",
        findings=findings,
        errors=tools.errors,
        trace=tools.trace,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    for key in (
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "DOCS_MCP_URL",
        "DOCS_TOKEN",
        "REQUESTS_MCP_URL",
        "REQUESTS_TOKEN",
        "SERVICE_MCP_URL",
        "SERVICE_MCP_TOKEN",
        "SERVICE_API_URL",
        "SERVICE_API_TOKEN",
    ):
        if not os.environ.get(key, "").strip():
            raise RuntimeError(f"Required environment variable is missing: {key}")
    yield


app = FastAPI(title="Resolver request agent", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "agent": "resolver"}


@app.post("/invoke", response_model=Result)
async def invoke(request: Invocation) -> Result:
    return await execute(request)
