"""AI tool definitions and execution dispatcher for verification."""

import json
import logging

from app.services.ddg_search import throttled_search

log = logging.getLogger("trabahero")

VERIFY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for information about a company, job posting, or person. "
                "Use to verify legitimacy, check SEC registration, find scam reports, "
                "or check social media presence."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "The search query. Be specific, e.g. "
                            "'ACME Corporation SEC registration Philippines'"
                        ),
                    }
                },
                "required": ["query"],
            },
        },
    }
]


def _format_results(results: list[dict]) -> str:
    """Format search results as a numbered list for the AI."""
    if not results:
        return "No results found."
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.get('title', '')}")
        if r.get("snippet"):
            lines.append(f"   {r['snippet'][:200]}")
        if r.get("url"):
            lines.append(f"   Source: {r['url']}")
    return "\n".join(lines)


async def execute_tool(name: str, args: dict) -> str:
    """Execute a tool call and return formatted results for the AI."""
    if name == "web_search":
        query = args.get("query", "")
        if not query:
            return "Error: empty query."
        log.info("[ai_tools] Searching: %s", query)
        results = await throttled_search(query, max_results=5)
        return _format_results(results)
    return f"Unknown tool: {name}"
