from typing import Any

from pydantic import BaseModel, Field


class GenerationOptions(BaseModel):
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, gt=0.0, le=1.0)
    max_tokens: int | None = Field(default=None, ge=1, le=8192)
    presence_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    frequency_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    stop: str | list[str] | None = None
    language: str = Field(default="ko", min_length=2, max_length=10)
    max_steps: int | None = Field(default=None, ge=1, le=20)


class AgentRunRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    options: GenerationOptions = Field(default_factory=GenerationOptions)


class AgentRunResponse(BaseModel):
    output: str
    steps: int
    model: str
    used_config: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(..., min_length=1)
    options: GenerationOptions = Field(default_factory=GenerationOptions)


class ChatResponse(BaseModel):
    session_id: str
    output: str
    steps: int
    model: str
    used_config: dict[str, Any] = Field(default_factory=dict)


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
