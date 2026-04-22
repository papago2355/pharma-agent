"""Multi-turn conversation runner for Korean RAG agents.

Domain-agnostic. The scenario supplies the system prompt, tool schemas,
and mock tool responses. The runner drives a normalized backend (see
backends.py) turn loop and records what the agent did so the grader can
assert against it.

The backend is selected via BENCHMARK_BACKEND env var, defaulting to
Anthropic. See backends.build_backend for details.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from backends import Backend, build_backend


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
    """Drives a multi-turn Korean conversation against an LLM backend
    with scripted mock tools.

    Limits
    ------
    - No streaming. We need the full stop_reason + tool_calls before
      grading.
    - max_tool_rounds guards against runaway loops from a broken mock.
    """

    def __init__(
        self,
        *,
        backend: Backend,
        mock_handler: MockHandler,
        max_tool_rounds_per_turn: int = 6,
    ) -> None:
        self._backend = backend
        self._mock = mock_handler
        self._max_rounds = max_tool_rounds_per_turn

    def turn(self, user_msg: str) -> TurnResult:
        self._backend.append_user(user_msg)
        result = TurnResult(user_msg=user_msg)
        rounds = 0
        while rounds < self._max_rounds:
            rounds += 1
            resp = self._backend.send()
            if resp.stop_reason != "tool_use":
                result.final_text = resp.text
                result.stop_reason = resp.stop_reason
                return result
            tool_results: list[tuple[str, str]] = []
            for call in resp.calls:
                result.tool_calls.append({"name": call.name, "input": call.input})
                content = self._mock(call.name, call.input)
                tool_results.append((call.id, content))
            self._backend.append_tool_results(tool_results)
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
    backend = build_backend(model=model, system=system, tools=tools)
    runner = ConversationRunner(backend=backend, mock_handler=mock_handler)
    out = RunResult(model=model, skill_injected=skill_injected)
    for u in user_turns:
        out.turns.append(runner.turn(u))
    return out
