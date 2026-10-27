import re

from datetime import datetime, timedelta, timezone

from app.models.schemas import Anomaly, ScanResponse
from app.services.anomaly_codes import clean_quote, normalise_code
from app.services.scanner.request_class import classify_request, facts_from_scan
from app.services.search import is_valid_company_name
# `risk_calculator` was retired 2026-10-17 and is deliberately not imported
# here. Leaving the import in with a `noqa` would be the half-wired state this
# project cares about most: reachable, working, and looking deliberate.


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
        out.append(Anomaly(
            flag=name,
            reasoning=reasoning,
            query_ref=str(f.get("query_ref") or "").strip(),
            # Normalised here rather than only in the parser: this is the last
            # gate before the wire, and a caller that builds the dict itself
            # would otherwise put an unchecked value on it.
            code=normalise_code(f.get("code")),
            quote=clean_quote(f.get("quote")),
            # The posting's own words for why it asks for a fee, screened the
            # same way as the quote: it is shown as something the posting said.
            fee_reason=clean_quote(f.get("fee_reason")),
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
    attributes = result.get("attributes", {})
    # No level here. The scan has read a document and nothing else: it has seen
    # no employer lookup, no retrieved page, nothing that could tell a reader
    # whether the posting's author is who they say they are. The level arrives
    # with the verification or offer analysis, and until one of those runs the
    # correct value is None - "not assessed" - which the panel already renders as
    # Unverified and resume matching already excludes. It used to be
    # `_posting_risk_from_flags` here, which meant a posting was given a
    # reassuring or alarming colour by a stage that had no evidence to base it
    # on, and the colour did not change when the evidence arrived.
    return ScanResponse(
        valid=result.get("valid", False),
        anomalies=flags,
        attributes=attributes,
        search_queries=list(result.get("search_queries") or []),
        job_summary=result.get("job_summary", ""),
        posting_analysis=result.get("posting_analysis", ""),
        company_name=company_name if company_name_validator(company_name) else None,
        error=result.get("error"),
        risk_score=None,
        risk_level=None,
        score_breakdown={},
        # What the posting asks for, decided here rather than by the model. The
        # scan is the stage that reads the posting, so it is the stage that has
        # the findings; the verify stage carries this value instead of
        # recomputing it from a list it only received second-hand.
        request_class=classify_request(facts_from_scan(flags, attributes)),
    )


def _scan_response(result: dict, company_name: str = "") -> ScanResponse:
    return _build_scan_response(
        result,
        company_name,
        anomalies_factory=_anomalies,
        company_name_validator=is_valid_company_name,
    )


_VALID_LINE_RE = re.compile(r"^\s*VALID\s*:\s*(true|false)\b", re.IGNORECASE | re.MULTILINE)
