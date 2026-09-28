"""Parser for the post-only verification output.

Blocks are located first and their fields extracted independently, rather than
matching the whole VERIFY/STATUS/DETAIL/END VERIFY shape in one regex. A single
combined regex loses a whole category whenever the model deviates slightly — a
missing END VERIFY on one block made the next match span two blocks and swallow
the one after it, and a status with trailing commentary after the word failed to
match at all. The user then saw a partial set of verification cards with nothing
in the log saying why.

The label and status are still both required before an item is emitted, so the
output contract the callers depend on is unchanged.
"""

import re

from app.models.schemas import VerificationItem

_BLOCK_SPLIT_RE = re.compile(r"^\s*VERIFY\s*:", re.IGNORECASE | re.MULTILINE)
_STATUS_RE = re.compile(r"\bSTATUS\s*:\s*\**\s*(green|yellow|red)\b", re.IGNORECASE)
_DETAIL_RE = re.compile(
    r"\bDETAIL\s*:\s*(.*?)(?=\s*END\s*VERIFY|\Z)",
    re.IGNORECASE | re.DOTALL,
)
# The label runs from just after VERIFY: up to whichever field comes first.
_LABEL_END_RE = re.compile(r"\b(?:STATUS|DETAIL)\s*:|\bEND\s*VERIFY", re.IGNORECASE)

# The categories the verify prompt asks for. A category that never arrived is
# logged rather than silently omitted from the panel.
EXPECTED_CATEGORIES = ("Company Existence", "Official Registration", "Reputation")

# Results recorded before the rename used "SEC Registration". Without this a
# stored verification would log a phantom missing category on every run.
# Values are lower-cased to match the comparison below.
_LEGACY_LABELS = {"sec registration": "official registration"}


def _blocks(text: str) -> list[str]:
    """Split the response into one chunk per VERIFY block."""
    starts = [m.start() for m in _BLOCK_SPLIT_RE.finditer(text)]
    if not starts:
        return []
    ends = starts[1:] + [len(text)]
    return [text[s:e] for s, e in zip(starts, ends)]


def _parse_verification_result(text: str) -> list[VerificationItem]:
    """Parse the labeled verification output into structured items."""
    if not text or not text.strip():
        return []

    items: list[VerificationItem] = []
    for block in _blocks(text):
        # Everything after the leading "VERIFY:" is the block body.
        body = block.split(":", 1)[1] if ":" in block else block

        end_match = re.search(r"\bSTATUS\s*:|\bDETAIL\s*:", body, re.IGNORECASE)
        label_source = body[: end_match.start()] if end_match else body
        label_end = _LABEL_END_RE.search(label_source)
        if label_end:
            label_source = label_source[: label_end.start()]
        label = " ".join(label_source.split()).strip(" -*\t")
        if not label:
            continue

        status_match = _STATUS_RE.search(block)
        if not status_match:
            continue

        detail_match = _DETAIL_RE.search(block)
        explanation = " ".join(detail_match.group(1).split()).strip() if detail_match else ""

        items.append(VerificationItem(
            label=label,
            status=status_match.group(1).strip().lower(),
            explanation=explanation,
        ))
    return items


def _parse_verify_section(text: str, name: str) -> str:
    """Extract a labeled REPORT/RECOMMENDATION section body. Returns '' if missing."""
    pattern = re.compile(
        rf"{name}:\s*(.+?)\s*END\s*{name}",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _missing_categories(items: list[VerificationItem]) -> list[str]:
    """Which expected categories the model did not actually report."""
    present = {
        _LEGACY_LABELS.get(i.label.strip().lower(), i.label.strip().lower())
        for i in items
    }
    return [c for c in EXPECTED_CATEGORIES if c.lower() not in present]
