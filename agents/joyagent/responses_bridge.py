"""Chat Completions <-> OpenAI Responses API translation for the LLM proxy.

JoyAgent only speaks /v1/chat/completions, but OpenAI's GPT-5.4 rejects
function tools together with reasoning_effort there. The proxy therefore
sends JoyAgent's chat requests to /v1/responses and turns the answer back
into a chat completion.

A response can hold a message and function calls at the same time (JoyAgent's
prompts ask for a short thought before each tool call); both are kept: the
text becomes `content`, the calls become `tool_calls`.

Reasoning items are requested in encrypted form (`store` is false) and cached
by the call ids of the function calls they preceded; when JoyAgent sends that
assistant turn back, they are put in front of it again, as OpenAI recommends
for reasoning models that call tools.

/responses has no `stop` (smolagents, used by the DataAgent's analysis tool,
sends one); the returned text is cut at the first stop sequence, as the chat
API does.
"""

from __future__ import annotations

import threading
import time
from typing import Any

# Chat parameters with no Responses counterpart, or handled separately.
_SKIP = {"messages", "tools", "tool_choice", "max_tokens", "max_completion_tokens",
         "reasoning_effort", "stream", "stream_options", "n", "model", "stop"}


def _text(content: Any) -> str:
    """Chat message content (string or list of parts) as plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts = []
    for part in content:
        if isinstance(part, dict) and part.get("type") in ("text", "input_text", "output_text"):
            parts.append(part.get("text") or "")
    return "".join(parts)


class ResponsesBridge:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reasoning: dict[str, list[dict[str, Any]]] = {}

    def reset(self) -> None:
        with self._lock:
            self._reasoning.clear()

    def to_responses(self, params: dict[str, Any], model: str) -> dict[str, Any]:
        instructions: list[str] = []
        items: list[dict[str, Any]] = []
        for i, msg in enumerate(params.get("messages") or []):
            role = msg.get("role")
            if role == "system":
                if not items:
                    instructions.append(_text(msg.get("content")))
                else:
                    items.append({"role": "developer", "content": _text(msg.get("content"))})
            elif role == "user":
                items.append({"role": "user", "content": _text(msg.get("content"))})
            elif role == "assistant":
                calls = msg.get("tool_calls") or []
                if calls:
                    with self._lock:
                        items.extend(self._reasoning.get(calls[0].get("id"), []))
                text = _text(msg.get("content"))
                if text:
                    items.append({"role": "assistant", "content": text})
                for call in calls:
                    fn = call.get("function") or {}
                    items.append({"type": "function_call", "call_id": call.get("id"),
                                  "name": fn.get("name"), "arguments": fn.get("arguments") or "{}"})
            elif role == "tool":
                items.append({"type": "function_call_output", "call_id": msg.get("tool_call_id"),
                              "output": _text(msg.get("content"))})

        body: dict[str, Any] = {
            "model": model,
            "input": items,
            "store": False,
            "include": ["reasoning.encrypted_content"],
        }
        if instructions:
            body["instructions"] = "\n\n".join(instructions)
        tools = []
        for tool in params.get("tools") or []:
            fn = tool.get("function") or {}
            tools.append({"type": "function", "name": fn.get("name"),
                          "description": fn.get("description") or "",
                          "parameters": fn.get("parameters") or {"type": "object", "properties": {}},
                          "strict": False})
        if tools:
            body["tools"] = tools
            choice = params.get("tool_choice")
            if isinstance(choice, dict):
                choice = {"type": "function", "name": (choice.get("function") or {}).get("name")}
            if choice is not None:
                body["tool_choice"] = choice
        max_out = params.get("max_completion_tokens") or params.get("max_tokens")
        if max_out:
            body["max_output_tokens"] = max_out
        if params.get("reasoning_effort"):
            body["reasoning"] = {"effort": params["reasoning_effort"]}
        for key, value in params.items():
            if key not in _SKIP:
                body[key] = value
        return body

    def to_chat(self, response: dict[str, Any], stop: str | list[str] | None = None) -> dict[str, Any]:
        reasoning: list[dict[str, Any]] = []
        texts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for item in response.get("output") or []:
            kind = item.get("type")
            if kind == "reasoning":
                reasoning.append({k: v for k, v in item.items() if k != "status"})
            elif kind == "message":
                for part in item.get("content") or []:
                    if part.get("type") == "output_text":
                        texts.append(part.get("text") or "")
            elif kind == "function_call":
                tool_calls.append({"id": item.get("call_id"), "type": "function",
                                   "function": {"name": item.get("name"),
                                                "arguments": item.get("arguments") or "{}"}})
        if tool_calls and reasoning:
            with self._lock:
                self._reasoning[tool_calls[0]["id"]] = reasoning

        text = "".join(texts)
        cuts = [text.find(s) for s in ([stop] if isinstance(stop, str) else stop or []) if s and s in text]
        if cuts:
            text = text[:min(cuts)]

        if tool_calls:
            finish = "tool_calls"
        elif response.get("status") == "incomplete" and not cuts:
            finish = "length"
        else:
            finish = "stop"
        message: dict[str, Any] = {"role": "assistant", "content": text or None}
        if tool_calls:
            message["tool_calls"] = tool_calls
        usage = response.get("usage") or {}
        return {
            "id": response.get("id"),
            "object": "chat.completion",
            "created": int(response.get("created_at") or time.time()),
            "model": response.get("model"),
            "choices": [{"index": 0, "message": message, "finish_reason": finish}],
            "usage": {
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "prompt_tokens_details": {
                    "cached_tokens": (usage.get("input_tokens_details") or {}).get("cached_tokens", 0)},
                "completion_tokens_details": {
                    "reasoning_tokens": (usage.get("output_tokens_details") or {}).get("reasoning_tokens", 0)},
            },
        }
