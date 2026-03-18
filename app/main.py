import json
from uuid import uuid4

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.agent import run_agent, stream_agent_run
from app.config import get_settings
from app.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    ModelsResponse,
)


app = FastAPI(title="Local LLM Agent API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: dict[str, list[dict]] = {}


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    try:
        resp = requests.get(settings.ollama_tags_url, timeout=settings.request_timeout)
        resp.raise_for_status()
        tags = resp.json().get("models", [])
        names = {item.get("name", "") for item in tags}
        return HealthResponse(
            status="ok",
            ollama_reachable=True,
            model_configured=settings.model_name,
            model_available=settings.model_name in names,
        )
    except Exception as exc:
        return HealthResponse(
            status="degraded",
            ollama_reachable=False,
            model_configured=settings.model_name,
            model_available=False,
            error=str(exc),
        )


@app.get("/models", response_model=ModelsResponse)
def models() -> ModelsResponse:
    settings = get_settings()
    try:
        resp = requests.get(settings.ollama_tags_url, timeout=settings.request_timeout)
        resp.raise_for_status()
        tags = resp.json().get("models", [])
        names = [item.get("name", "") for item in tags if item.get("name")]
        return ModelsResponse(default_model=settings.model_name, available_models=names)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not query Ollama models: {exc}") from exc


@app.post("/agent/run", response_model=AgentRunResponse)
def agent_run(payload: AgentRunRequest) -> AgentRunResponse:
    settings = get_settings()
    try:
        output, steps, used_model, _ = run_agent(payload.prompt, settings, model=payload.model)
        return AgentRunResponse(output=output, steps=steps, model=used_model)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent run failed: {exc}") from exc


@app.post("/agent/run/stream")
def agent_run_stream(payload: AgentRunRequest) -> StreamingResponse:
    settings = get_settings()

    def event_stream():
        try:
            stream, used_model = stream_agent_run(payload.prompt, settings, model=payload.model)
            yield f"event: start\ndata: {json.dumps({'model': used_model}, ensure_ascii=False)}\n\n"
            for event in stream:
                event_type = event.get("type")
                if event_type == "char":
                    yield f"event: token\ndata: {json.dumps({'char': event.get('char', '')}, ensure_ascii=False)}\n\n"
                elif event_type == "tool":
                    yield f"event: tool\ndata: {json.dumps({'name': event.get('name', '')}, ensure_ascii=False)}\n\n"
                elif event_type == "done":
                    yield f"event: done\ndata: {json.dumps({'steps': event.get('steps', 0)}, ensure_ascii=False)}\n\n"
                    yield "event: done\ndata: [DONE]\n\n"
                    return
            yield "event: done\ndata: [DONE]\n\n"
        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/agent/chat", response_model=ChatResponse)
def agent_chat(payload: ChatRequest) -> ChatResponse:
    settings = get_settings()
    session_id = payload.session_id or str(uuid4())
    history = sessions.get(session_id, [])

    try:
        output, steps, used_model, updated_messages = run_agent(
            payload.message,
            settings,
            model=payload.model,
            history=history,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent chat failed: {exc}") from exc

    sessions[session_id] = [msg for msg in updated_messages if msg.get("role") in {"user", "assistant", "tool"}][-20:]
    return ChatResponse(session_id=session_id, output=output, steps=steps, model=used_model)
