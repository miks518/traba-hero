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

Two states that look identical from outside are deliberately distinguished:
a response that was read and contained no checks returns an empty list, and a
response that could not be read at all raises. Returning an empty list for
unreadable text is what let a failed verification render as a panel with nothing
on it and no error anywhere.
"""

import re

from app.models.schemas import VerificationItem

from .verification_prompt import VERIFY_CLAIM_CATEGORIES

_BLOCK_SPLIT_RE = re.compile(r"^\s*VERIFY\s*:", re.IGNORECASE | re.MULTILINE)
_STATUS_RE = re.compile(r"\bSTATUS\s*:\s*\**\s*(green|yellow|red)\b", re.IGNORECASE)
# FINDING is the new field name; DETAIL is the legacy one. Both are accepted so a
# provider that answers in prose either way still yields an explanation — a card
# with a status and no explanation reads as a finding that says nothing.
_DETAIL_RE = re.compile(
    r"\b(?:DETAIL|FINDING)\s*:\s*(.*?)(?=\s*SOURCE\s*:|\s*END\s*VERIFY|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_SOURCE_RE = re.compile(
    r"\bSOURCE\s*:\s*(.*?)\|\s*(https?://\S+)(?=\s*END\s*VERIFY|\Z)",
    re.IGNORECASE | re.DOTALL,
)
# The label runs from just after VERIFY: up to whichever field comes first.
_LABEL_END_RE = re.compile(
    r"\b(?:STATUS|DETAIL|FINDING|SOURCE)\s*:|\bEND\s*VERIFY", re.IGNORECASE
)

# The categories the verify prompt asks for, so a category that never arrived is
# logged rather than silently omitted from the panel. It is a *diagnostic* list
# and nothing more: parsing below accepts whatever label it is given, because a
# result recorded before a rename carries a label this tuple no longer names.
# Derived from the prompt module rather than restated, since three places naming
# the categories is how they drifted apart once already.
EXPECTED_CATEGORIES = VERIFY_CLAIM_CATEGORIES

# Results recorded before the rename used "SEC Registration". Without this a
# stored verification would log a phantom missing category on every run.
# Values are lower-cased to match the comparison below.
_LEGACY_LABELS = {"sec registration": "official registration"}


class VerificationParseError(RuntimeError):
    """The response could not be read at all.

    Distinct from a well-formed response that reported no checks. The first is a
    failure worth reporting; the second is a legitimate empty result that the
    verification flow renders with its own notice.
    """


def _blocks(text: str) -> list[str]:
    """Split the response into one chunk per VERIFY block."""
    starts = [m.start() for m in _BLOCK_SPLIT_RE.finditer(text)]
    if not starts:
        return []
    ends = starts[1:] + [len(text)]
    return [text[s:e] for s, e in zip(starts, ends)]


def _parse_verification_result(text: str) -> list[VerificationItem]:
    """Parse the labeled verification output into structured items.

    Raises `VerificationParseError` when the text contains no VERIFY block at
    all. Returning an empty list for unparseable text is what let a failed
    verification render as a panel with nothing on it and no error.
    """
    if not text or not text.strip():
        raise VerificationParseError("empty response")

    blocks = _blocks(text)
    if not blocks:
        raise VerificationParseError("no VERIFY block in the response")

    items: list[VerificationItem] = []
    for block in blocks:
        # Everything after the leading "VERIFY:" is the block body.
        body = block.split(":", 1)[1] if ":" in block else block

        end_match = re.search(
            r"\bSTATUS\s*:|\bDETAIL\s*:|\bFINDING\s*:", body, re.IGNORECASE
        )
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

        source_title = ""
        source_url = ""
        source_match = _SOURCE_RE.search(block)
        if source_match:
            source_title = " ".join(source_match.group(1).split()).strip()
            source_url = source_match.group(2).strip()

        items.append(VerificationItem(
            label=label,
            status=status_match.group(1).strip().lower(),
            explanation=explanation,
            source_title=source_title,
            source_url=source_url,
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
