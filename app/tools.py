import json
import subprocess
from pathlib import Path

from app.schemas import ToolResult


MAX_FILE_CHARS = 12000
MAX_TOOL_OUTPUT_CHARS = 12000
ALLOWED_COMMAND_PREFIXES = {
    "ls",
    "pwd",
    "python",
    "python3",
    "node",
    "npm",
    "git status",
}


def _safe_path(base_dir: Path, user_path: str) -> Path:
    target = (base_dir / user_path).resolve()
    if not str(target).startswith(str(base_dir.resolve())):
        raise ValueError("path escapes tool working directory")
    return target


def list_files(base_dir: Path, path: str = ".") -> ToolResult:
    try:
        target = _safe_path(base_dir, path)
        if not target.exists():
            return ToolResult(ok=False, output="path does not exist")
        if target.is_file():
            return ToolResult(ok=True, output=str(target.relative_to(base_dir)))

        entries = []
        for item in sorted(target.iterdir(), key=lambda x: x.name.lower()):
            suffix = "/" if item.is_dir() else ""
            entries.append(f"{item.name}{suffix}")
        return ToolResult(ok=True, output="\n".join(entries)[:MAX_TOOL_OUTPUT_CHARS])
    except Exception as exc:
        return ToolResult(ok=False, output=f"list_files error: {exc}")


def read_file(base_dir: Path, path: str) -> ToolResult:
    try:
        target = _safe_path(base_dir, path)
        if not target.exists() or target.is_dir():
            return ToolResult(ok=False, output="file not found")

        content = target.read_text(encoding="utf-8", errors="replace")
        if len(content) > MAX_FILE_CHARS:
            content = content[:MAX_FILE_CHARS] + "\n...<truncated>"
        return ToolResult(ok=True, output=content, meta={"path": str(target.relative_to(base_dir))})
    except Exception as exc:
        return ToolResult(ok=False, output=f"read_file error: {exc}")


def run_shell(base_dir: Path, command: str) -> ToolResult:
    command = command.strip()
    if not command:
        return ToolResult(ok=False, output="empty command")

    is_allowed = any(command == allowed or command.startswith(f"{allowed} ") for allowed in ALLOWED_COMMAND_PREFIXES)
    if not is_allowed:
        return ToolResult(ok=False, output="command blocked by policy")

    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=base_dir,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        output = output[:MAX_TOOL_OUTPUT_CHARS]
        return ToolResult(ok=completed.returncode == 0, output=output or "<no output>", meta={"returncode": completed.returncode})
    except Exception as exc:
        return ToolResult(ok=False, output=f"run_shell error: {exc}")


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories under a relative path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path from TOOL_WORKDIR."}
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file under TOOL_WORKDIR.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path from TOOL_WORKDIR."}
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a safe shell command using a restricted allow-list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Allowed commands like ls, pwd, python3, node, npm."}
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
]


def execute_tool(base_dir: Path, name: str, arguments: str) -> str:
    try:
        payload = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError:
        return json.dumps(ToolResult(ok=False, output="invalid JSON arguments").model_dump())

    if name == "list_files":
        result = list_files(base_dir, path=payload.get("path", "."))
    elif name == "read_file":
        result = read_file(base_dir, path=payload.get("path", ""))
    elif name == "run_shell":
        result = run_shell(base_dir, command=payload.get("command", ""))
    else:
        result = ToolResult(ok=False, output=f"unknown tool: {name}")

    return json.dumps(result.model_dump())
