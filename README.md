# local-agent-lab

Local LLM Agent API template using FastAPI + Ollama (OpenAI-compatible) and a small Streamlit docs UI.

## 1) Setup

```bash
cd /home/kajj8808/local-agent-lab
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 2) Start Ollama and pull a model

```bash
ollama serve
```

In another terminal:

```bash
ollama pull qwen2.5-coder:7b
```

If you use a different model, update `MODEL_NAME` in `.env`.

## 3) Run API server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open FastAPI docs:

- http://localhost:8000/docs
- http://localhost:8000/redoc

## 4) Run Streamlit docs/test UI

```bash
streamlit run streamlit_app.py --server.port 8501
```

Open:

- http://localhost:8501
- Left sidebar menu: `Playground`, `API Docs`, `LangChain`
- LangChain page includes both invoke and stream demos

## API endpoints

- `GET /health`: check Ollama connectivity and configured model availability.
- `GET /models`: list models from Ollama tags.
- `POST /agent/run`: one-shot agent execution.
- `POST /agent/run/stream`: one-shot SSE streaming (`text/event-stream`, character chunks) after tool-enabled agent execution.
- `POST /agent/chat`: session-based chat agent.

## Example requests

```bash
curl http://localhost:8000/health
```

```bash
curl -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{"prompt":"현재 디렉토리 파일 목록 보여줘"}'
```

```bash
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"README 읽고 요약해줘"}'
```

```bash
curl -N -X POST http://localhost:8000/agent/run/stream \
  -H "Content-Type: application/json" \
  -d '{"prompt":"한글자씩 스트리밍 테스트"}'
```

## Notes

- Tools are intentionally restricted for safety (`list_files`, `read_file`, allow-listed `run_shell`).
- Session memory is in-memory only; restart clears chat sessions.
- For better quality, consider larger local models if VRAM allows.
- Streaming endpoint emits `start`, `token`, `tool`, and `done` SSE events.
- LangChain smoke test in Streamlit uses Ollama OpenAI URL (`http://localhost:11434/v1`) directly.
- API Docs page includes Python/JS streaming client examples.
