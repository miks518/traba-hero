"""An ordinary contact channel coded with the escape valve is not a finding.

Field report 2026-11-04: a posting with a confirmed employer, a clean reputation
and an ordinary ask read Caution on three separate scans. The finding was "applies
via a personal Gmail address" / "informal application through direct message",
coded `OTHER`.

The prompt forbids flagging either — three rules, and a test that keeps the "on
their own" carve-out from returning. The model reached for `OTHER` anyway, and
`OTHER` is what did the damage: `request_class._class_for`'s catch-all returns
`unclassified`, which the grid prices yellow in every establishment state.

No new code was added. `anomaly_codes` admits a code only with a confirmed claim
and citation behind it, and the honest answer here is that there is no finding —
not that there is a differently-named one.

**The drop is scoped to the escape codes.** A finding the taxonomy named
correctly is the taxonomy working, and this gate is only about a labelling miss.
"""

import pytest

from app.services.scanner.scan_result import _anomalies, _is_ordinary_channel_flagged


def _finding(label: str, reasoning: str = "", code: str = "OTHER",
             quote: str = "") -> dict:
    # The quote is English-language and ordinary by default, so a test about the
    # *channel* guardrail cannot be failed by the *money* guardrail reading the
    # same span. A Gmail quote beside a FEE_MANDATORY finding is an invented fee
    # by that guard's definition, correctly.
    return {"flag": label, "reasoning": reasoning, "code": code,
            "quote": quote or "HIRING! Customer service rep, Makati."}


@pytest.mark.parametrize("label,reasoning", [
    ("Applies via a personal Gmail address", "The posting asks applicants to email a Gmail address"),
    ("Informal application through direct message", "Applicants reply by direct message"),
    ("Asks applicants to apply via Messenger", "The posting says to message the page"),
    ("Uses a free email domain", ""),
    ("", "The posting directs applicants to a Yahoo account"),
    # The phrase only in the reasoning, which is the case that fails if the
    # guard reads the label alone. The model writes the same finding with the
    # name in either field: "Requires an informal application" says nothing on
    # its face, and the channel is only named in the sentence under it.
    ("Requires an informal application", "Applicants message a Gmail account to apply"),
    ("Uses a non-company contact", "The address given is a free email domain"),
])
def test_an_ordinary_channel_coded_other_is_dropped(label, reasoning):
    assert _anomalies([_finding(label, reasoning)]) == []


def test_an_empty_code_is_dropped_too():
    """Absent and `OTHER` are different claims, but both are escape states and
    both reach the same catch-all.
    """
    assert _anomalies([_finding("Applies via a Gmail address", code="")]) == []


@pytest.mark.parametrize("label,reasoning,code", [
    ("Asks applicants to pay a processing fee", "A fee is required before the interview", "FEE_MANDATORY"),
    ("Sends documents to a non-employer domain", "Resumes go to forms.hiredocs.net", "DOCUMENTS_VIA_THIRD_PARTY"),
    ("Ordinary applicant packet", "2x2 photo and NBI clearance required", "APPLICATION_DOCUMENTS"),
    ("Pays per task completed", "Pay is stated per video liked", "TASK_FOR_EARNING"),
    ("Presents as a government office", "Names a national agency", "IMPERSONATES_AUTHORITY"),
])
def test_a_correctly_coded_finding_survives_even_when_it_names_a_channel(label, reasoning, code):
    """The gate reads the code before the text. A real finding that happens to
    mention messaging — or that arrives beside a Gmail address — is kept.
    """
    quote = "Pay P350 processing fee via GCash." if code == "FEE_MANDATORY" else ""
    out = _anomalies([_finding(label, reasoning, code, quote=quote)])
    assert len(out) == 1
    assert out[0].flag == label


def test_the_scope_is_the_escape_code_only():
    """The function's contract, stated separately from the drop, because a wider
    scope would silently swallow correctly-coded findings.
    """
    assert _is_ordinary_channel_flagged("Gmail address", "", "OTHER") is True
    assert _is_ordinary_channel_flagged("Gmail address", "", "") is True
    assert _is_ordinary_channel_flagged("Gmail address", "", "FEE_MANDATORY") is False
    assert _is_ordinary_channel_flagged("Gmail address", "", "APPLICATION_DOCUMENTS") is False


def test_a_clean_posting_with_only_a_gmail_other_is_ordinary():
    """End to end: the field report, at the gate every consumer reads downstream
    of. The request class is what the grid prices, so `ordinary` here is the
    difference between green and Caution.
    """
    from app.services.scanner.scan_result import _scan_response

    response = _scan_response({
        "valid": True,
        "anomalies": [_finding(
            "Applies via a personal Gmail address",
            "The posting asks applicants to email a Gmail address",
        )],
        "attributes": {},
    }, "Acme Corp")

    assert response.anomalies == []
    assert response.request_class == "ordinary"


def test_a_real_finding_beside_a_dropped_one_survives():
    """The drop is per finding. A posting asking for a fee *and* naming a Gmail
    address keeps the fee.
    """
    out = _anomalies([
        _finding("Applies via a Gmail address", ""),
        _finding("Asks applicants to pay a processing fee", "A fee is required",
                 "FEE_MANDATORY", quote="Pay P350 processing fee via GCash."),
    ])
    assert [a.code for a in out] == ["FEE_MANDATORY"]
