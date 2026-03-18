# local-agent-lab

FastAPI + Ollama(OpenAI 호환) 기반의 로컬 LLM Agent API 템플릿입니다.

- 핵심 API: `/health`, `/models`, `/agent/run`, `/agent/run/stream`, `/agent/chat`
- 스트리밍: SSE(`start`/`tool`/`token`/`done`)
- 문서/테스트 UI: Streamlit(좌측 카드형 메뉴)

## 1) 설치

```bash
cd /home/kajj8808/local-agent-lab
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 2) 환경 변수

`.env.example` 기준:

```env
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_TAGS_URL=http://localhost:11434/api/tags
MODEL_NAME=qwen2.5-coder:7b
TEMPERATURE=0.1
MAX_STEPS=6
TOOL_WORKDIR=.
API_KEY=
REQUEST_TIMEOUT=60
```

주요 값:

- `MODEL_NAME`: 기본 모델
- `MAX_STEPS`: 에이전트 추론/툴 호출 최대 단계
- `TOOL_WORKDIR`: 툴 접근 루트 디렉토리

## 3) Ollama 실행

터미널 1:

```bash
ollama serve
```

터미널 2:

```bash
ollama pull qwen2.5-coder:7b
```

## 4) API 서버 실행

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

문서:

- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 5) Streamlit 문서/테스트 UI 실행

```bash
streamlit run streamlit_app.py --server.port 8501
```

접속:

- http://localhost:8501
- 좌측 메뉴: `Playground`, `API Docs`, `LangChain`

## 6) API 엔드포인트

- `GET /health`: Ollama 연결 및 기본 모델 사용 가능 여부
- `GET /models`: Ollama 모델 목록
- `POST /agent/run`: one-shot 에이전트 실행
- `POST /agent/run/stream`: SSE 스트리밍(one-shot)
- `POST /agent/chat`: 세션형 대화(현재 메모리 기반)

## 7) 요청 예시

```bash
curl http://localhost:8000/health
```

```bash
curl -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{"prompt":"현재 디렉토리 파일 목록 보여줘","options":{"model":"qwen2.5-coder:7b","temperature":0.1,"language":"ko","top_p":0.9,"max_tokens":512,"max_steps":6}}'
```

```bash
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"README 읽고 요약해줘","options":{"language":"ko","temperature":0.1}}'
```

```bash
curl -N -X POST http://localhost:8000/agent/run/stream \
  -H "Content-Type: application/json" \
  -d '{"prompt":"한글자씩 스트리밍 테스트","options":{"language":"ko","temperature":0.1}}'
```

### 7.1 외부 클라이언트에서 조절 가능한 옵션

`options` 객체로 아래 값을 요청마다 제어할 수 있습니다.

- `model`
- `temperature`
- `top_p`
- `max_tokens`
- `presence_penalty`
- `frequency_penalty`
- `stop` (문자열 또는 문자열 배열)
- `language` (`ko`, `en` 등)
- `max_steps`

영어로 응답이 튀는 경우, `options.language`를 `ko`로 고정하고 `temperature`를 낮추면 안정성이 좋아집니다.

## 8) 스트리밍(SSE) 수신 형식

예시:

```text
event: start
data: {"model":"qwen2.5-coder:7b","used_config":{"language":"ko","temperature":0.1}}

event: tool
data: {"name":"list_files"}

event: token
data: {"char":"안"}

event: done
data: [DONE]
```

핵심 포인트:

- `curl`은 `-N` 옵션 사용(버퍼링 방지)
- 클라이언트에서 `event:`/`data:` 라인 단위로 파싱
- `data: [DONE]` 수신 시 종료

## 9) WSL2 외부 접속(중요)

WSL 내부에서 `--host 0.0.0.0`으로 띄워도, 외부에서 바로 안 열릴 수 있습니다.

### 9.1 같은 PC(Windows 브라우저)에서 접속

대부분 `http://localhost:8000`으로 바로 접속됩니다.

### 9.2 같은 네트워크의 다른 기기에서 접속

Windows 관리자 PowerShell에서 포트 포워딩 + 방화벽 허용이 필요합니다.

1) WSL IP 확인(WSL 터미널):

```bash
hostname -I
```

2) 포트 포워딩(Windows 관리자 PowerShell):

```powershell
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8000 connectaddress=<WSL_IP> connectport=8000
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8501 connectaddress=<WSL_IP> connectport=8501
```

3) 방화벽 규칙 추가(Windows 관리자 PowerShell):

```powershell
netsh advfirewall firewall add rule name="local-agent-api-8000" dir=in action=allow protocol=TCP localport=8000
netsh advfirewall firewall add rule name="local-agent-docs-8501" dir=in action=allow protocol=TCP localport=8501
```

4) 외부 기기에서 접속:

- API: `http://<WINDOWS_IP>:8000`
- Streamlit: `http://<WINDOWS_IP>:8501`

참고:

- 재부팅/WSL 재시작 시 WSL IP가 바뀔 수 있어 `portproxy` 재설정이 필요할 수 있습니다.
- 인터넷 공개가 목적이면 라우터 포트포워딩 또는 터널(예: Cloudflare Tunnel/ngrok) 구성이 필요합니다.

## 10) 참고 사항

- 툴 실행은 안전을 위해 제한됨(`list_files`, `read_file`, allow-list 기반 `run_shell`)
- `/agent/chat` 세션은 메모리 기반(서버 재시작 시 초기화)
- LangChain은 API 서버에 강결합하기보다, 실제 서비스 레이어에서 사용하는 구성을 권장
