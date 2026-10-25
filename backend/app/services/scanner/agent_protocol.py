"""The agent's tool-call protocol: labeled text, not native tool calls.

`lm_client.chat()` returns `completion.choices[0].message.content` and nothing
else: it has no `tools=` parameter and no multi-turn support of its own, and
native tool calling is not guaranteed across OpenRouter routes. The repo's
precedent for a missing capability is to fall back rather than fail, so the
agent's tool calls are a labeled text block with its own parser — the `===`
problem, one level up, closed the way `format_results()` closes it and
`verification_parser.py` parses its fallback:

    TOOL: search
    ARGUMENT: knollridges company or employer

A turn is one of two shapes and no third: labeled tool calls, or the
structured final answer. Anything else is an answer attempt the structured
parser will reject, which the harness reports as an unreadable answer — a
finding the model can recover from, not a crash.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.scanner.search_planner import search_query_is_safe

# The two tools the agent has. §4.3: two tools, both code-owned, both metered.
TOOLS = ("search", "fetch")

_TOOL_LINE_RE = re.compile(r"^\s*TOOL\s*:\s*(?P<name>[A-Za-z_]+)\s*$")
_ARGUMENT_LINE_RE = re.compile(r"^\s*ARGUMENT\s*:\s*(?P<argument>.*)$")
# Detection, not parsing: a turn that opens a tool block is a tool-call turn
# even when every call in it is refused (the harness tells the model so,
# rather than reading the turn as its answer).
_TOOL_BLOCK_RE = re.compile(r"^\s*TOOL\s*:", re.MULTILINE)


@dataclass(frozen=True)
class ToolCall:
    name: str
    argument: str


def parse_tool_calls(text: str) -> tuple[ToolCall, ...]:
    """Every well-formed tool call in the turn's text, in order.

    A call is a `TOOL:` line naming one of this agent's two tools followed by
    an `ARGUMENT:` line carrying its one argument. A call that names a tool
    the agent does not have, or carries no argument, is dropped rather than
    repaired — the harness would only refuse it a step later, and a refusal
    the model cannot see explained teaches it nothing.

    A search argument that carries a conclusion word is dropped at the same
    door: the query-safety rule is a control here, before the credit is
    spent, in every mode. It governs what we *search for*, not where a search
    result may point, so a `fetch` argument is not filtered by it.
    """
    calls: list[ToolCall] = []
    pending: str | None = None
    for line in (text or "").splitlines():
        tool = _TOOL_LINE_RE.match(line)
        if tool:
            pending = tool.group("name").strip().lower()
            continue
        argument = _ARGUMENT_LINE_RE.match(line)
        if argument and pending is not None:
            name, pending = pending, None
            value = argument.group("argument").strip()
            if name not in TOOLS or not value:
                continue
            if name == "search" and not search_query_is_safe(value):
                continue
            calls.append(ToolCall(name=name, argument=value))
    return tuple(calls)


def is_final_answer(text: str) -> bool:
    """Whether the turn's text is the final answer rather than tool calls.

    A turn that opens a tool block is a tool-call turn even when every call
    in it was refused: the harness must tell the model the query was refused
    so it can choose another, not read the turn as an answer and hand prose
    to the structured-output parser.
    """
    return not _TOOL_BLOCK_RE.search(text or "")
