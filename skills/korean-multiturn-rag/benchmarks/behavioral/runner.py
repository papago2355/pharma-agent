"""Multi-turn conversation runner for Korean RAG agents.

Domain-agnostic. The scenario supplies the system prompt, tool schemas,
and mock tool responses. The runner drives the Anthropic API turn loop
and records what the agent did so the grader can assert against it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable

import anthropic


@dataclass
class TurnResult:
    user_msg: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    final_text: str = ""
    stop_reason: str = ""


@dataclass
class RunResult:
    model: str
    skill_injected: bool
    turns: list[TurnResult] = field(default_factory=list)


MockHandler = Callable[[str, dict[str, Any]], str]
# (tool_name, tool_input) -> tool_result_content_as_string


class ConversationRunner:
    """Drives a multi-turn Korean conversation against an Anthropic model
    with scripted mock tools.

    Limits
    ------
    - No streaming. We need the full stop_reason + tool_use blocks before
      grading.
    - max_tool_rounds guards against runaway loops from a broken mock.
    """

    def __init__(
        self,
        *,
        model: str,
        system: str,
        tools: list[dict[str, Any]],
        mock_handler: MockHandler,
        max_tokens: int = 2048,
        max_tool_rounds_per_turn: int = 6,
    ) -> None:
        self._client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self._model = model
        self._system = system
        self._tools = tools
        self._mock = mock_handler
        self._max_tokens = max_tokens
        self._max_rounds = max_tool_rounds_per_turn
        self._messages: list[dict[str, Any]] = []

    def turn(self, user_msg: str) -> TurnResult:
        self._messages.append({"role": "user", "content": user_msg})
        result = TurnResult(user_msg=user_msg)
        rounds = 0
        while rounds < self._max_rounds:
            rounds += 1
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=self._system,
                tools=self._tools,
                messages=self._messages,
            )
            self._messages.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason != "tool_use":
                result.final_text = "".join(
                    b.text for b in resp.content if getattr(b, "type", "") == "text"
                )
                result.stop_reason = resp.stop_reason
                return result
            tool_results = []
            for block in resp.content:
                if getattr(block, "type", "") != "tool_use":
                    continue
                call = {"name": block.name, "input": dict(block.input)}
                result.tool_calls.append(call)
                content = self._mock(block.name, dict(block.input))
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": content}
                )
            self._messages.append({"role": "user", "content": tool_results})
        # Exceeded tool-round budget; treat as a failure mode for grading.
        result.stop_reason = "max_tool_rounds_exceeded"
        return result


def run_scenario(
    *,
    model: str,
    system: str,
    tools: list[dict[str, Any]],
    mock_handler: MockHandler,
    user_turns: list[str],
    skill_injected: bool,
) -> RunResult:
    runner = ConversationRunner(
        model=model, system=system, tools=tools, mock_handler=mock_handler
    )
    out = RunResult(model=model, skill_injected=skill_injected)
    for u in user_turns:
        out.turns.append(runner.turn(u))
    return out
