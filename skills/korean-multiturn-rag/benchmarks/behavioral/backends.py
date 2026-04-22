"""LLM backends for the conversation runner.

Abstracts the two protocols we care about:

- AnthropicBackend:  `anthropic` SDK, `messages.create`, native tool_use blocks.
- OpenAICompatBackend: `openai` SDK against any OpenAI-compatible endpoint
                      (vLLM, SGLang, hosted OSS providers). Normalizes
                      tool_calls back into the Anthropic-shaped calls the
                      runner expects.

The runner only sees the normalized view — the scenarios keep their
existing Anthropic-style `{name, description, input_schema}` tool
definitions, and each backend translates as needed.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class NormalizedCall:
    """Tool call in the shape the runner + grader consume."""
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class NormalizedResponse:
    text: str                         # empty if model called tools instead
    calls: list[NormalizedCall]       # empty if model answered with text
    stop_reason: str                  # "tool_use" | "end_turn" | other


class Backend(ABC):
    """Stateful per-conversation client.

    Each backend owns its own message-history buffer in its native format,
    so the runner doesn't need to know about Anthropic vs OpenAI history
    differences. Callers append user input via `append_user` + tool
    outputs via `append_tool_results`, and poll `send` to advance.
    """

    @abstractmethod
    def append_user(self, text: str) -> None: ...

    @abstractmethod
    def append_tool_results(
        self, results: list[tuple[str, str]]  # [(tool_call_id, content_str)]
    ) -> None: ...

    @abstractmethod
    def send(self) -> NormalizedResponse: ...


# ---------------------------------------------------------------- Anthropic


class AnthropicBackend(Backend):
    def __init__(
        self,
        *,
        model: str,
        system: str,
        tools: list[dict[str, Any]],
        max_tokens: int = 2048,
    ) -> None:
        import anthropic

        self._client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )
        self._model = model
        self._system = system
        self._tools = tools  # native Anthropic shape already
        self._max_tokens = max_tokens
        self._messages: list[dict[str, Any]] = []
        self._last_response: Any = None

    def append_user(self, text: str) -> None:
        self._messages.append({"role": "user", "content": text})

    def append_tool_results(self, results: list[tuple[str, str]]) -> None:
        self._messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": tcid, "content": content}
                    for tcid, content in results
                ],
            }
        )

    def send(self) -> NormalizedResponse:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=self._system,
            tools=self._tools,
            messages=self._messages,
        )
        self._messages.append({"role": "assistant", "content": resp.content})
        self._last_response = resp
        calls: list[NormalizedCall] = []
        text_parts: list[str] = []
        for block in resp.content:
            btype = getattr(block, "type", "")
            if btype == "tool_use":
                calls.append(
                    NormalizedCall(id=block.id, name=block.name, input=dict(block.input))
                )
            elif btype == "text":
                text_parts.append(block.text)
        return NormalizedResponse(
            text="".join(text_parts),
            calls=calls,
            stop_reason=resp.stop_reason or "",
        )


# ---------------------------------------------------------------- OpenAI-compat


def _to_openai_tool(tool: dict[str, Any]) -> dict[str, Any]:
    """Convert Anthropic-style tool def to OpenAI function-calling shape."""
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
        },
    }


class OpenAICompatBackend(Backend):
    """For vLLM / SGLang / any OpenAI-compatible chat-completions endpoint.

    Requires the server to have been started with
    `--enable-auto-tool-choice --tool-call-parser <family>`.
    """

    def __init__(
        self,
        *,
        model: str,
        system: str,
        tools: list[dict[str, Any]],
        base_url: str,
        api_key: str = "EMPTY",
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> None:
        import openai

        self._client = openai.OpenAI(base_url=base_url, api_key=api_key)
        self._model = model
        self._tools = [_to_openai_tool(t) for t in tools]
        self._max_tokens = max_tokens
        self._temperature = temperature
        # Initial system prompt lives in the messages list for OpenAI-shape.
        self._messages: list[dict[str, Any]] = [
            {"role": "system", "content": system}
        ]
        # We remember the last assistant tool_calls so we can resolve
        # ids when the user submits tool_results.
        self._pending_tool_calls: list[dict[str, Any]] = []

    def append_user(self, text: str) -> None:
        self._messages.append({"role": "user", "content": text})

    def append_tool_results(self, results: list[tuple[str, str]]) -> None:
        # OpenAI spec: one {"role": "tool", ...} message per tool_call_id.
        for tcid, content in results:
            self._messages.append(
                {"role": "tool", "tool_call_id": tcid, "content": content}
            )

    def send(self) -> NormalizedResponse:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=self._messages,
            tools=self._tools,
            tool_choice="auto",
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )
        msg = resp.choices[0].message
        finish = resp.choices[0].finish_reason or ""

        # Persist the assistant turn EXACTLY as returned, including any
        # tool_calls, so the follow-up tool messages reference the right ids.
        assistant_entry: dict[str, Any] = {
            "role": "assistant",
            "content": msg.content or "",
        }
        tool_calls = getattr(msg, "tool_calls", None) or []
        if tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in tool_calls
            ]
        self._messages.append(assistant_entry)

        calls: list[NormalizedCall] = []
        for tc in tool_calls:
            # Arguments arrive as a JSON *string*. Best-effort parse; if
            # malformed we pass the raw string through as a debugging aid.
            raw = tc.function.arguments or "{}"
            try:
                parsed = json.loads(raw)
                if not isinstance(parsed, dict):
                    parsed = {"_raw": raw}
            except json.JSONDecodeError:
                parsed = {"_raw": raw}
            calls.append(
                NormalizedCall(id=tc.id, name=tc.function.name, input=parsed)
            )

        # Normalize stop reason to Anthropic vocabulary.
        if finish == "tool_calls" or calls:
            stop = "tool_use"
        elif finish == "stop":
            stop = "end_turn"
        else:
            stop = finish

        return NormalizedResponse(
            text=msg.content or "",
            calls=calls,
            stop_reason=stop,
        )


# ---------------------------------------------------------------- Factory


def build_backend(
    *,
    model: str,
    system: str,
    tools: list[dict[str, Any]],
    max_tokens: int = 2048,
) -> Backend:
    """Select backend via BENCHMARK_BACKEND env var.

    - 'anthropic' (default): AnthropicBackend.
    - 'openai_compat':       OpenAICompatBackend, needs BENCHMARK_BASE_URL.
    """
    backend = os.environ.get("BENCHMARK_BACKEND", "anthropic").lower()
    if backend == "anthropic":
        return AnthropicBackend(
            model=model, system=system, tools=tools, max_tokens=max_tokens
        )
    if backend in ("openai_compat", "openai", "vllm"):
        base_url = os.environ.get("BENCHMARK_BASE_URL")
        if not base_url:
            raise RuntimeError(
                "BENCHMARK_BACKEND=openai_compat requires BENCHMARK_BASE_URL "
                "(e.g. http://localhost:8200/v1 for a local vLLM)."
            )
        api_key = os.environ.get("BENCHMARK_API_KEY", "EMPTY")
        return OpenAICompatBackend(
            model=model,
            system=system,
            tools=tools,
            base_url=base_url,
            api_key=api_key,
            max_tokens=max_tokens,
        )
    raise ValueError(f"Unknown BENCHMARK_BACKEND={backend!r}")
