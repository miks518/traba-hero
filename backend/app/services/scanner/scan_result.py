import re

from app.models.schemas import RedFlag, ScanResponse
from app.services.ddg_search import is_valid_company_name


def _red_flags(flags: list) -> list[RedFlag]:
    out: list[RedFlag] = []
    if not isinstance(flags, list):
        return out
    for f in flags:
        if isinstance(f, str):
            f = {"flag": f}
        if not isinstance(f, dict):
            continue
        name = str(f.get("flag") or "").strip()
        if not name:
            continue
        reasoning = str(f.get("reasoning") or "").strip()
        severity = str(f.get("severity") or "").strip().lower()
        out.append(RedFlag(flag=name, reasoning=reasoning, severity=severity or "mid"))
    return out


def _language_instruction(language: str) -> str:
    lang = (language or "").strip().lower()
    if lang in ("tagalog", "filipino", "tl"):
        return "Respond in Tagalog. Write the JOB SUMMARY, and all RED FLAG label/reasoning in Tagalog. Keep the VALID and section labels exactly as shown above."
    return "Respond in English."


def _build_scan_response(
    result: dict,
    company_name: str,
    *,
    red_flags_factory,
    company_name_validator,
) -> ScanResponse:
    flags = red_flags_factory(result.get("red_flags", []))
    return ScanResponse(
        valid=result.get("valid", False),
        red_flags=flags,
        job_summary=result.get("job_summary", ""),
        company_name=company_name if company_name_validator(company_name) else None,
        error=result.get("error"),
    )


def _scan_response(result: dict, company_name: str = "") -> ScanResponse:
    return _build_scan_response(
        result,
        company_name,
        red_flags_factory=_red_flags,
        company_name_validator=is_valid_company_name,
    )


_VALID_LINE_RE = re.compile(r"^\s*VALID\s*:\s*(true|false)\b", re.IGNORECASE | re.MULTILINE)
