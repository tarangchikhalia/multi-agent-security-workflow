"""Local HTTP adapter for the Documentation skill runner."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .contract import Invocation, Result
from .runner import execute


@asynccontextmanager
async def lifespan(app: FastAPI):
    for key in ("OPENAI_API_KEY", "OPENAI_MODEL", "DOCS_MCP_URL", "DOCS_TOKEN"):
        if not os.environ.get(key, "").strip():
            raise RuntimeError(f"Required environment variable is missing: {key}")
    yield


app = FastAPI(title="Documentation agent", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "agent": "documentation"}


@app.post("/invoke", response_model=Result)
async def invoke(request: Invocation) -> Result:
    return await execute(request)
