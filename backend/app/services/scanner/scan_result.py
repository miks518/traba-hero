import re

from datetime import datetime, timedelta, timezone

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
        out.append(Anomaly(
            flag=name,
            reasoning=reasoning,
            severity=severity or "mid",
            query_ref=str(f.get("query_ref") or "").strip(),
        ))
    return out


def _language_instruction(language: str) -> str:
    lang = (language or "").strip().lower()
    if lang in ("tagalog", "filipino", "tl"):
        return "Respond in Tagalog. Write the JOB SUMMARY, and all ANOMALY label/reasoning in Tagalog. Keep the VALID and section labels exactly as shown above."
    return "Respond in English."


# The product's subject is the Philippine labour market, so "today" is Manila's
# day, not the deployment server's. A fixed offset rather than `ZoneInfo`,
# because `zoneinfo` needs the tzdata package on Windows and this is not worth a
# dependency that can be missing at import. Philippines has no daylight saving,
# so UTC+8 is exact rather than an approximation.
_PHILIPPINES = timezone(timedelta(hours=8))


def _today_instruction() -> str:
    """Tell the model what day it is, and what that is for.

    A scan reported "future-dated hiring event - the poster advertises a hiring
    event scheduled for October 14, 2026, which is a date far in the future".
    It was 12 October. The date was two days away.

    The model was not being careless, it was working without a reference: nothing
    in either prompt told it what today is, so "far in the future" had nothing to
    be far from. Its training data ends at some unknown earlier date, so any date
    it cannot place looks remote. It then applied a genuinely useful scam
    heuristic - fake postings do claim distant start dates - to an input that did
    not deserve it.

    This is the cheap fix and it costs about fifteen tokens, against hundreds for
    enabling reasoning on every scan. It is worth doing whatever the reasoning
    setting is, because a reasoning model still cannot place a date it was never
    given.

    The static prompt says anomalies are about what the posting contains. Saying
    *when* the posting is being read is input, not a rule, so it lives here
    beside the language instruction rather than in `SYSTEM_PROMPT.md` - which
    also keeps the two prompt copies from drifting on a value that changes daily.
    """
    today = datetime.now(_PHILIPPINES)
    return (
        f"Today is {today.strftime('%A, %d %B %Y')} ({today:%Y-%m-%d}), Philippine time. "
        "Use this whenever the posting mentions a date, a schedule, a deadline or a "
        "duration. A date is only an anomaly if it is genuinely far from today - a "
        "date within the next few days is ordinary and must not be reported. "
        "Report an ordinary near-term date as no anomaly at all."
    )


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
        attributes=result.get("attributes", {}),
        search_queries=list(result.get("search_queries") or []),
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
