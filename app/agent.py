import json
from pathlib import Path
from typing import Any, Iterator, cast

from openai import OpenAI

from app.config import Settings
from app.tools import TOOL_DEFINITIONS, execute_tool


SYSTEM_PROMPT = (
    "You are a local coding agent. "
    "Use tools when needed, keep answers concise, and always return a final user-facing answer. "
    "When tool use is needed and native tool calling is unavailable, return JSON with keys 'name' and 'arguments'."
)


def _extract_json_tool_call(content: str | None) -> tuple[str, str] | None:
    if not content:
        return None

    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    name = payload.get("name")
    arguments = payload.get("arguments", {})
    if not isinstance(name, str) or not name:
        return None
    if not isinstance(arguments, dict):
        return None

    return name, json.dumps(arguments)


def _client(settings: Settings) -> OpenAI:
    return OpenAI(
        base_url=settings.ollama_base_url,
        api_key=settings.api_key or "ollama",
        timeout=settings.request_timeout,
    )


def run_agent(
    user_prompt: str,
    settings: Settings,
    model: str | None = None,
    history: list[dict] | None = None,
) -> tuple[str, int, str, list[dict]]:
    target_model = model or settings.model_name
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_prompt})

    client = _client(settings)
    base_dir = Path(settings.tool_workdir).resolve()

    for step in range(1, settings.max_steps + 1):
        completion = client.chat.completions.create(
            model=target_model,
            messages=cast(Any, messages),
            tools=cast(Any, TOOL_DEFINITIONS),
            tool_choice="auto",
            temperature=settings.temperature,
        )
        message = completion.choices[0].message

        tool_calls = message.tool_calls or []
        normalized_tool_calls: list[Any] = [tc for tc in tool_calls if getattr(tc, "function", None) is not None]
        if not normalized_tool_calls:
            fallback = _extract_json_tool_call(message.content)
            if fallback:
                name, args_json = fallback
                tool_result = execute_tool(base_dir, name, args_json)
                messages.append({"role": "assistant", "content": message.content or ""})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"Tool result for {name}:\n{tool_result}\n"
                            "Continue. If done, provide the final answer to the user."
                        ),
                    }
                )
                continue

            final_text = message.content or ""
            messages.append({"role": "assistant", "content": final_text})
            return final_text, step, target_model, messages

        assistant_payload = {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in normalized_tool_calls
            ],
        }
        messages.append(assistant_payload)

        for tool_call in normalized_tool_calls:
            tool_result = execute_tool(base_dir, tool_call.function.name, tool_call.function.arguments)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": tool_result,
                }
            )

    return (
        "Reached max reasoning steps. Please retry with a simpler request or increase MAX_STEPS.",
        settings.max_steps,
        target_model,
        messages,
    )


def stream_agent_run(user_prompt: str, settings: Settings, model: str | None = None) -> tuple[Iterator[dict[str, Any]], str]:
    target_model = model or settings.model_name
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}]

    client = _client(settings)

    def _event_generator() -> Iterator[dict[str, Any]]:
        for step in range(1, settings.max_steps + 1):
            stream = client.chat.completions.create(
                model=target_model,
                messages=cast(Any, messages),
                tools=cast(Any, TOOL_DEFINITIONS),
                tool_choice="auto",
                temperature=settings.temperature,
                stream=True,
            )

            collected_text_parts: list[str] = []
            tool_calls: dict[int, dict[str, str]] = {}

            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                content = delta.content or ""
                if content:
                    collected_text_parts.append(content)
                    for ch in content:
                        yield {"type": "char", "char": ch}

                delta_tool_calls = getattr(delta, "tool_calls", None) or []
                for tc in delta_tool_calls:
                    idx = getattr(tc, "index", 0)
                    current = tool_calls.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                    if getattr(tc, "id", None):
                        current["id"] = tc.id
                    func = getattr(tc, "function", None)
                    if func is not None:
                        if getattr(func, "name", None):
                            current["name"] = func.name
                        if getattr(func, "arguments", None):
                            current["arguments"] += func.arguments

            final_text = "".join(collected_text_parts)
            normalized_tool_calls = [
                payload
                for _, payload in sorted(tool_calls.items(), key=lambda x: x[0])
                if payload.get("name")
            ]

            if not normalized_tool_calls:
                fallback = _extract_json_tool_call(final_text)
                if fallback:
                    name, args_json = fallback
                    tool_result = execute_tool(Path(settings.tool_workdir).resolve(), name, args_json)
                    messages.append({"role": "assistant", "content": final_text})
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Tool result for {name}:\n{tool_result}\n"
                                "Continue. If done, provide the final answer to the user."
                            ),
                        }
                    )
                    yield {"type": "tool", "name": name}
                    continue

                yield {"type": "done", "steps": step}
                return

            assistant_payload = {
                "role": "assistant",
                "content": final_text,
                "tool_calls": [
                    {
                        "id": item["id"] or f"call_{i}",
                        "type": "function",
                        "function": {"name": item["name"], "arguments": item["arguments"] or "{}"},
                    }
                    for i, item in enumerate(normalized_tool_calls)
                ],
            }
            messages.append(assistant_payload)

            for item in normalized_tool_calls:
                tool_name = item["name"]
                tool_args = item.get("arguments", "{}")
                tool_result = execute_tool(Path(settings.tool_workdir).resolve(), tool_name, tool_args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": item.get("id") or "",
                        "name": tool_name,
                        "content": tool_result,
                    }
                )
                yield {"type": "tool", "name": tool_name}

        yield {"type": "done", "steps": settings.max_steps}

    return _event_generator(), target_model
