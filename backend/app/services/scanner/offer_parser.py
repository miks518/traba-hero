"""Parser for the post-only analysis output.

The format is five single lines ending in END, which keeps the parsable surface
small. Anything unparseable is handled by the caller's failsafe, so a model that
reorders or rewords the output degrades to a generic analysis rather than an
error screen.
"""

import re

from .offer_prompt import NOT_OFFER_KIND

_FIELDS = ("KIND", "VERDICT", "WHAT IT ASKS", "WHAT IT OFFERS", "WHAT TO CHECK")
_LINE_RE = re.compile(r"^\s*(KIND|VERDICT|WHAT\s+IT\s+ASKS|WHAT\s+IT\s+OFFERS|WHAT\s+TO\s+CHECK)\s*:\s*(.+?)\s*$", re.IGNORECASE)


def _parse_analyze_offer(text: str) -> dict | None:
    """Parse the labeled analysis output into a dict, or None if unreadable."""
    if not text or not text.strip():
        return None

    captured: dict[str, str] = {}
    for line in text.splitlines():
        match = _LINE_RE.match(line)
        if not match:
            continue
        key = " ".join(match.group(1).split()).upper()
        if key in _FIELDS and key not in captured:
            captured[key] = match.group(2).strip()

    if not captured.get("KIND") or not captured.get("VERDICT"):
        return None

    return {
        "kind": captured["KIND"],
        "verdict": captured["VERDICT"],
        "what_it_asks": captured.get("WHAT IT ASKS", ""),
        "what_it_offers": captured.get("WHAT IT OFFERS", ""),
        "what_to_check": captured.get("WHAT TO CHECK", ""),
        "is_offer": captured["KIND"].strip().upper() != NOT_OFFER_KIND,
    }
