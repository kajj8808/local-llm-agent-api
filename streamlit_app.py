import json

import requests
import streamlit as st
from pydantic import SecretStr

try:
    from langchain_openai import ChatOpenAI
except Exception:
    ChatOpenAI = None


def _render_playground(api_base: str):
    st.subheader("Playground")
    st.caption("Run endpoints and inspect stream events in real time.")

    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("Health: GET /health", use_container_width=True):
            try:
                res = requests.get(f"{api_base}/health", timeout=30)
                st.json(res.json())
            except Exception as exc:
                st.error(str(exc))

        if st.button("Models: GET /models", use_container_width=True):
            try:
                res = requests.get(f"{api_base}/models", timeout=30)
                st.json(res.json())
            except Exception as exc:
                st.error(str(exc))

        st.markdown("### One-shot")
        run_prompt = st.text_area("Prompt", value="현재 디렉토리 파일 목록 보여줘", key="run_prompt")
        run_model = st.text_input("Model (optional)", value="", key="run_model")
        run_temp = st.slider("Temperature", min_value=0.0, max_value=2.0, value=0.1, step=0.1, key="run_temp")
        run_lang = st.selectbox("Language", ["ko", "en", "ja"], index=0, key="run_lang")
        if st.button("POST /agent/run", use_container_width=True):
            body = {
                "prompt": run_prompt,
                "options": {
                    "temperature": run_temp,
                    "language": run_lang,
                },
            }
            if run_model.strip():
                body["options"]["model"] = run_model.strip()
            try:
                res = requests.post(f"{api_base}/agent/run", json=body, timeout=120)
                st.json(res.json())
            except Exception as exc:
                st.error(str(exc))

    with col_b:
        st.markdown("### Stream (1-char SSE)")
        stream_prompt = st.text_area("Stream Prompt", value="현재 디렉토리 파일 목록 보여줘", key="stream_prompt")
        stream_model = st.text_input("Stream model (optional)", value="", key="stream_model")
        stream_temp = st.slider("Stream Temperature", min_value=0.0, max_value=2.0, value=0.1, step=0.1, key="stream_temp")
        stream_lang = st.selectbox("Stream Language", ["ko", "en", "ja"], index=0, key="stream_lang")

        stream_output = st.empty()
        stream_tools = st.empty()

        if st.button("POST /agent/run/stream", use_container_width=True):
            body = {
                "prompt": stream_prompt,
                "options": {
                    "temperature": stream_temp,
                    "language": stream_lang,
                },
            }
            if stream_model.strip():
                body["options"]["model"] = stream_model.strip()

            text_buf = ""
            tool_logs: list[str] = []
            current_event = ""

            try:
                with requests.post(f"{api_base}/agent/run/stream", json=body, stream=True, timeout=180) as res:
                    res.raise_for_status()
                    for raw in res.iter_lines(decode_unicode=True):
                        if raw is None:
                            continue
                        line = raw.strip()
                        if not line:
                            continue

                        if line.startswith("event: "):
                            current_event = line[7:].strip()
                            continue

                        if not line.startswith("data: "):
                            continue

                        payload = line[6:]
                        if payload == "[DONE]":
                            break

                        try:
                            item = json.loads(payload)
                        except Exception:
                            continue

                        if current_event == "token":
                            ch = item.get("char")
                            if isinstance(ch, str):
                                text_buf += ch
                                stream_output.text_area("Stream Output", value=text_buf, height=260)
                        elif current_event == "tool":
                            tool_name = item.get("name", "unknown")
                            tool_logs.append(f"tool called: {tool_name}")
                            stream_tools.code("\n".join(tool_logs), language="text")
                        elif current_event == "error":
                            st.error(item.get("error", "unknown error"))
                            break
            except Exception as exc:
                st.error(str(exc))

    st.markdown("### Chat")
    session_id = st.text_input("Session ID (optional)", value="")
    chat_msg = st.text_area("Message", value="README 파일 읽어줘")
    chat_model = st.text_input("Chat model (optional)", value="")
    chat_temp = st.slider("Chat Temperature", min_value=0.0, max_value=2.0, value=0.1, step=0.1, key="chat_temp")
    chat_lang = st.selectbox("Chat Language", ["ko", "en", "ja"], index=0, key="chat_lang")
    if st.button("POST /agent/chat", use_container_width=True):
        body = {
            "message": chat_msg,
            "options": {
                "temperature": chat_temp,
                "language": chat_lang,
            },
        }
        if session_id.strip():
            body["session_id"] = session_id.strip()
        if chat_model.strip():
            body["options"]["model"] = chat_model.strip()
        try:
            res = requests.post(f"{api_base}/agent/chat", json=body, timeout=120)
            st.json(res.json())
        except Exception as exc:
            st.error(str(exc))


def _render_api_docs(api_base: str):
    st.subheader("API Docs")
    st.caption("Readable endpoint reference with streaming usage guide.")

    st.markdown("#### Base URL")
    st.code(api_base, language="text")

    st.markdown("#### Endpoints")
    st.markdown(
        """
| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Ollama reachability + configured model status |
| GET | `/models` | Available local model list from Ollama |
| POST | `/agent/run` | One-shot tool-enabled agent response |
| POST | `/agent/run/stream` | SSE stream (`start`/`tool`/`token`/`done`) |
| POST | `/agent/chat` | Session-based chat |
"""
    )

    with st.expander("POST /agent/run", expanded=True):
        st.markdown("**지원 옵션**: `model`, `temperature`, `top_p`, `max_tokens`, `presence_penalty`, `frequency_penalty`, `stop`, `language`, `max_steps`")
        st.markdown("**Request**")
        st.code(
            '{"prompt":"현재 디렉토리 파일 목록 보여줘","options":{"model":"qwen2.5-coder:7b","temperature":0.1,"language":"ko","top_p":0.9,"max_tokens":512,"max_steps":6}}',
            language="json",
        )
        st.markdown("**Response**")
        st.code(
            '{"output":"...","steps":2,"model":"qwen2.5-coder:7b","used_config":{"language":"ko","temperature":0.1}}',
            language="json",
        )

    with st.expander("POST /agent/run/stream", expanded=True):
        st.markdown("**Request**")
        st.code('{"prompt":"현재 디렉토리 파일 목록 보여줘","options":{"language":"ko","temperature":0.1}}', language="json")
        st.markdown("**How it works (very short)**")
        st.markdown(
            """
1. `POST` 요청을 보냅니다 (`stream=True` 또는 SSE client).
2. 서버가 `event: start`를 먼저 보냅니다.
3. 필요하면 `event: tool`이 오고, 이어서 `event: token`이 반복됩니다.
4. `data: [DONE]`가 오면 종료입니다.
"""
        )
        st.markdown("**SSE events (response stream format)**")
        st.code(
            """event: start
data: {"model":"qwen2.5-coder:7b","used_config":{"language":"ko"}}

event: tool
data: {"name":"list_files"}

event: token
data: {"char":"f"}

event: done
data: [DONE]""",
            language="text",
        )

        st.markdown("**Python client example**")
        st.code(
            """import json
import requests

url = "http://localhost:8000/agent/run/stream"
body = {"prompt": "현재 디렉토리 파일 목록 보여줘", "options": {"language": "ko", "temperature": 0.1}}

event = ""
with requests.post(url, json=body, stream=True, timeout=180) as r:
    r.raise_for_status()
    for raw in r.iter_lines(decode_unicode=True):
        if not raw:
            continue
        line = raw.strip()
        if line.startswith("event: "):
            event = line[7:]
            continue
        if not line.startswith("data: "):
            continue
        data = line[6:]
        if data == "[DONE]":
            break
        payload = json.loads(data)
        if event == "token":
            print(payload.get("char", ""), end="", flush=True)
""",
            language="python",
        )

        st.markdown("**JavaScript client example (browser EventSource)**")
        st.code(
            """// If your backend supports GET SSE endpoints, EventSource is easiest.
// For this POST SSE endpoint, use fetch + ReadableStream parser instead.

const res = await fetch("http://localhost:8000/agent/run/stream", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({ prompt: "현재 디렉토리 파일 목록 보여줘", options: { language: "ko", temperature: 0.1 } })
});

const reader = res.body.getReader();
const decoder = new TextDecoder();
let buf = "";
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  buf += decoder.decode(value, { stream: true });
  // parse SSE lines from buf and handle event/data pairs
}
""",
            language="javascript",
        )

        st.markdown("**Common mistakes**")
        st.markdown(
            """
- `curl` must use `-N` (no buffer), otherwise output appears at once.
- Python `requests.post(..., stream=True)` is required.
- Parse SSE by `event:` + `data:` lines, not as a single JSON response.
- `data: [DONE]` means stream end.
"""
        )

    with st.expander("Copy Curl", expanded=False):
        st.code(
            """curl -X POST http://localhost:8000/agent/run \\
  -H 'Content-Type: application/json' \\
  -d '{"prompt":"프로젝트 파일 목록 알려줘"}'

curl -N -X POST http://localhost:8000/agent/run/stream \\
  -H 'Content-Type: application/json' \\
  -d '{"prompt":"현재 디렉토리 파일 목록 보여줘"}'""",
            language="bash",
        )

    st.info("FastAPI Swagger: http://localhost:8000/docs")


def _render_langchain(api_base: str, ollama_base: str):
    st.subheader("LangChain")
    st.caption("Check connectivity first, then run an actual LangChain invocation.")

    st.markdown("#### 1) Connectivity Check")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Check Agent API (/health)", use_container_width=True):
            try:
                res = requests.get(f"{api_base}/health", timeout=20)
                st.json(res.json())
            except Exception as exc:
                st.error(f"Agent API check failed: {exc}")
    with c2:
        if st.button("Check Ollama (/api/tags)", use_container_width=True):
            try:
                tags_url = ollama_base.rstrip("/").replace("/v1", "") + "/api/tags"
                res = requests.get(tags_url, timeout=20)
                st.json(res.json())
            except Exception as exc:
                st.error(f"Ollama check failed: {exc}")

    st.markdown("#### 2) LangChain Example")
    lc_model = st.text_input("LangChain model", value="qwen2.5-coder:7b")
    lc_prompt = st.text_area("Prompt", value="Respond exactly with LC_OK")
    st.code(
        """from langchain_openai import ChatOpenAI
from pydantic import SecretStr

llm = ChatOpenAI(
    model="qwen2.5-coder:7b",
    base_url="http://localhost:11434/v1",
    api_key=SecretStr("ollama"),
    temperature=0,
)

res = llm.invoke("Respond exactly with LC_OK")
print(res.content)""",
        language="python",
    )

    if ChatOpenAI is None:
        st.warning("`langchain-openai` not installed. Run `pip install -r requirements.txt`.")
        return

    if st.button("Run LangChain Smoke Test", use_container_width=True):
        try:
            llm = ChatOpenAI(
                model=lc_model,
                base_url=ollama_base,
                api_key=SecretStr("ollama"),
                temperature=0,
            )
            res = llm.invoke(lc_prompt)
            content = str(getattr(res, "content", "")).strip()
            st.text_area("LangChain Response", value=content, height=180)
            if content == "LC_OK":
                st.success("Smoke test passed (exact match: LC_OK)")
            else:
                st.info("Connected, but response is not exact LC_OK. Model is still reachable.")
        except Exception as exc:
            st.error(f"LangChain test failed: {exc}")

    st.markdown("#### 3) LangChain Streaming Demo")
    stream_prompt = st.text_input("Streaming prompt", value="한 글자씩 천천히 LC_STREAM_OK를 출력해줘")
    if st.button("Run LangChain Stream", use_container_width=True):
        if ChatOpenAI is None:
            st.warning("`langchain-openai` not installed.")
            return
        out = st.empty()
        acc = ""
        try:
            llm = ChatOpenAI(
                model=lc_model,
                base_url=ollama_base,
                api_key=SecretStr("ollama"),
                temperature=0,
                streaming=True,
            )
            for chunk in llm.stream(stream_prompt):
                piece = str(getattr(chunk, "content", ""))
                if not piece:
                    continue
                for ch in piece:
                    acc += ch
                    out.text_area("LangChain Stream Output", value=acc, height=180)
            if acc.strip():
                st.success("LangChain stream finished")
            else:
                st.info("No streamed text received")
        except Exception as exc:
            st.error(f"LangChain stream failed: {exc}")


st.set_page_config(page_title="Local Agent API Docs", page_icon=":robot_face:", layout="wide")

st.title("Local LLM Agent API")
st.caption("FastAPI + Ollama + Tool-calling agent")

api_base_input = st.sidebar.text_input("Agent API Base URL", value="http://localhost:8000")
ollama_base_input = st.sidebar.text_input("Ollama OpenAI Base URL", value="http://localhost:11434/v1")

if "page" not in st.session_state:
    st.session_state.page = "Playground"

st.sidebar.markdown("### Navigation")

nav_items = [
    ("Playground", "Run API directly", "Try one-shot, chat, and SSE stream", "🧪"),
    ("API Docs", "Integration guide", "See request/response and SSE parsing", "📘"),
    ("LangChain", "Framework examples", "Smoke test and streaming demo", "🔗"),
]

for idx, (title, subtitle, desc, icon) in enumerate(nav_items):
    with st.sidebar.container(border=True):
        st.markdown(f"**{icon} {title}**")
        st.caption(subtitle)
        st.caption(desc)
        is_current = st.session_state.page == title
        btn_label = "Current page" if is_current else f"Open {title}"
        if st.button(btn_label, key=f"nav_open_{idx}", use_container_width=True, disabled=is_current):
            st.session_state.page = title
            st.rerun()

page = st.session_state.page

if page == "Playground":
    _render_playground(api_base_input)
elif page == "API Docs":
    _render_api_docs(api_base_input)
else:
    _render_langchain(api_base_input, ollama_base_input)
