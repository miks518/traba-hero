import re

from app.models.schemas import VerificationItem


def _parse_verification_result(text: str) -> list[VerificationItem]:
    """Parse the AI's labeled verification output into structured items."""
    items = []
    pattern = re.compile(
        r"VERIFY:\s*(.+?)\s*STATUS:\s*(green|yellow|red)\s*DETAIL:\s*(.+?)\s*END\s*VERIFY",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(text):
        items.append(VerificationItem(
            label=match.group(1).strip(),
            status=match.group(2).strip().lower(),
            explanation=match.group(3).strip(),
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
