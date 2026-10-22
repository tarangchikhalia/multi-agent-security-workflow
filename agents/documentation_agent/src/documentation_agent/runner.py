"""Bounded Responses API loop with an explicit, typed Docs-only dispatcher."""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Annotated, Any

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contract import Invocation, Result
from .tools import ResourceTools

logger = logging.getLogger(__name__)
Key = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[\w.-]+$")]
Title = Annotated[str, Field(min_length=1, max_length=200, pattern=r"\S")]
Body = Annotated[str, Field(min_length=1, max_length=100_000, pattern=r"\S")]


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ListDocuments(Arguments):
    search: str = Field(default="", max_length=200)
    limit: int = Field(default=50, ge=1, le=100)


class GetDocument(Arguments):
    document_id: Key


class CreateDocument(Arguments):
    title: Title
    body: Body
    owner: Key


class UpdateDocument(Arguments):
    document_id: Key
    title: Title | None = None
    body: Body | None = None

    @model_validator(mode="after")
    def require_change(self):
        if self.title is None and self.body is None:
            raise ValueError("Provide title or body")
        return self


TOOL_ARGUMENTS = {
    "list_documents": ListDocuments,
    "get_document": GetDocument,
    "create_document": CreateDocument,
    "update_document": UpdateDocument,
}


def definitions() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": name,
            "description": getattr(ResourceTools, name).__doc__,
            "parameters": arguments.model_json_schema(),
            "strict": False,
        }
        for name, arguments in TOOL_ARGUMENTS.items()
    ]


async def execute(request: Invocation) -> Result:
    tools = ResourceTools({"docs": (os.environ["DOCS_MCP_URL"], os.environ["DOCS_TOKEN"])})
    findings: list[str] = []
    summary = ""
    # New local history on every invocation; no previous_response_id or stored responses.
    history: list[Any] = [
        {"role": "user", "content": f"Task: {request.task}\nContext: {request.context}"}
    ]
    try:
        async with asyncio.timeout(request.timeout_seconds):
            model = os.environ["OPENAI_MODEL"].removeprefix("openai/")
            async with AsyncOpenAI(max_retries=0, timeout=request.timeout_seconds) as client:
                for _ in range(request.max_model_calls):
                    response = await client.responses.create(
                        model=model,
                        instructions=Path(__file__).with_name("SKILL.md").read_text(),
                        input=history,
                        tools=definitions(),  # type: ignore[arg-type]
                        store=False,
                    )
                    if response.status != "completed":
                        raise RuntimeError("Model response incomplete")
                    calls = []
                    for item in response.output:
                        if item.type == "function_call":
                            calls.append(item)
                        elif item.type == "message":
                            for part in item.content:
                                if part.type == "output_text" and part.text.strip():
                                    findings.append(part.text)
                        elif item.type != "reasoning":
                            raise ValueError("Unsupported model output")
                    if not calls:
                        summary = response.output_text.strip()
                        if not summary:
                            raise ValueError("Model did not return a final answer")
                        break
                    if len(calls) > 12:
                        raise ValueError("Too many tool calls")
                    # Validate the whole batch before executing any writes.
                    validated = []
                    for call in calls:
                        schema = TOOL_ARGUMENTS.get(call.name)
                        if (
                            schema is None
                            or not call.call_id
                            or call.call_id in {item.call_id for item, _ in validated}
                        ):
                            raise ValueError("Unknown tool or invalid call ID")
                        arguments = schema.model_validate_json(call.arguments)
                        validated.append((call, arguments.model_dump()))
                    history.extend(item.model_dump(mode="json") for item in response.output)
                    for call, arguments in validated:
                        result = await tools.call("docs", call.name, arguments)
                        history.append(
                            {
                                "type": "function_call_output",
                                "call_id": call.call_id,
                                "output": json.dumps(result),
                            }
                        )
                else:
                    tools.errors.append("Model turn limit exceeded")
    except TimeoutError:
        tools.errors.append(
            "Invocation deadline exceeded; verify document state before retrying writes"
        )
    except Exception as error:
        error_type = type(error).__name__
        logger.error("Documentation invocation failed: error_type=%s", error_type)
        tools.errors.append(
            f"Agent execution failed ({error_type}); check model and resource configuration"
        )
    return Result(
        run_id=request.run_id,
        status="failed" if tools.errors else "completed",
        summary="Documentation task failed; partial findings are available"
        if tools.errors
        else summary,
        findings=findings,
        errors=tools.errors,
        trace=tools.trace,
    )
