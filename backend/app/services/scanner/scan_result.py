import re

from app.models.schemas import Anomaly, ScanResponse
from app.services.search import is_valid_company_name
from .risk_calculator import _posting_risk_from_flags


def _anomalies(flags: list) -> list[Anomaly]:
    out: list[Anomaly] = []
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
        out.append(Anomaly(flag=name, reasoning=reasoning, severity=severity or "mid"))
    return out


def _language_instruction(language: str) -> str:
    lang = (language or "").strip().lower()
    if lang in ("tagalog", "filipino", "tl"):
        return "Respond in Tagalog. Write the JOB SUMMARY, and all ANOMALY label/reasoning in Tagalog. Keep the VALID and section labels exactly as shown above."
    return "Respond in English."


def _build_scan_response(
    result: dict,
    company_name: str,
    *,
    anomalies_factory,
    company_name_validator,
) -> ScanResponse:
    # Falls back to the pre-rename key so a cached or recorded parse result
    # still produces its anomalies rather than silently scoring a clean posting.
    flags = anomalies_factory(
        result.get("anomalies", result.get("red_flags", []))
    )
    # The posting's own indicators always produce a verdict, so the panel has a
    # number from the moment the scan returns rather than waiting on an employer
    # lookup that may not be possible.
    score, level, breakdown = _posting_risk_from_flags(flags)
    return ScanResponse(
        valid=result.get("valid", False),
        anomalies=flags,
        job_summary=result.get("job_summary", ""),
        posting_analysis=result.get("posting_analysis", ""),
        company_name=company_name if company_name_validator(company_name) else None,
        error=result.get("error"),
        risk_score=score,
        risk_level=level,
        score_breakdown=breakdown,
    )


def _scan_response(result: dict, company_name: str = "") -> ScanResponse:
    return _build_scan_response(
        result,
        company_name,
        anomalies_factory=_anomalies,
        company_name_validator=is_valid_company_name,
    )


_VALID_LINE_RE = re.compile(r"^\s*VALID\s*:\s*(true|false)\b", re.IGNORECASE | re.MULTILINE)
