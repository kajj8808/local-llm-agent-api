from typing import Any

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    model: str | None = None


class AgentRunResponse(BaseModel):
    output: str
    steps: int
    model: str


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(..., min_length=1)
    model: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    output: str
    steps: int
    model: str


class HealthResponse(BaseModel):
    status: str
    ollama_reachable: bool
    model_configured: str
    model_available: bool
    error: str | None = None


class ModelsResponse(BaseModel):
    default_model: str
    available_models: list[str]


class ToolResult(BaseModel):
    ok: bool
    output: str
    meta: dict[str, Any] = Field(default_factory=dict)
