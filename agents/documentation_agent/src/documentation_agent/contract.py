from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


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
