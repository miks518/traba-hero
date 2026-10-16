"""A citation the search provider never returned is not evidence.

`VERIFY_PROMPT.md` says a `source_url` must be "copied exactly from the results"
and that "a constructed URL is a fabricated citation". That sentence is the whole
of the enforcement, and `test_verify.py:558-570` asserts it only as a string in
the prompt — it never supplies a result set, so it would pass if every URL were
discarded or every URL were invented.

Two defects share this boundary.

**A — the citation is unbound.** Both the structured path
(`verification_flow.py`) and the labeled-text fallback (`verification_parser.py`)
copy a model-returned URL to the wire without comparing it to anything. The
normaliser that would make the comparison trivial already exists:
`search.py:_canonical_url`, written and tested for the dedupe at `search.py:211`
and used for nothing else.

**B — the score is unbound, and this is the larger half.** `risk_calculator`
never reads `source_url`; it scores any `red` item by its category weight. A `red`
citing nothing scores the same 25 points as a `red` citing a retrieved page. The
project's own rule is that a `red` requires "a provided search result that
actually contradicts a claim the posting made", and nothing in code required it.

B is fixed by demoting an unbacked `red` to `yellow`, because `yellow` already
carries zero weight in `risk_calculator` — so the calculator needs no change and
the existing semantics are the ones being enforced. An unbacked `red` is exactly
what the codebase calls a claim nobody could confirm, and that is `yellow`.

These call `_read_verify_output` directly. It is a pure function over a string, so
no provider, no key, and no network is involved.
"""

import pytest

from app.models.schemas import VerificationItem
from app.services.scanner.risk_calculator import _refutation_score_from_verify
from app.services.scanner.verification_flow import _read_verify_output

RETRIEVED = "https://employer.example/about"


def _json_response(url: str, status: str = "red", category: str = "Channel Match") -> str:
    import json

    return json.dumps({
        "checks": [{
            "category": category,
            "status": status,
            "finding": "The posting directs applicants to a personal account.",
            "source_title": "About us",
            "source_url": url,
        }],
        "evidence": [{"title": "About us", "url": url, "snippet": "we are hiring"}],
        "report": "r",
        "recommendation": "x",
    })


def _read(url: str, status: str = "red", allowed=(RETRIEVED,)):
    items, _report, _rec, _json, evidence, _level, _score = _read_verify_output(
        _json_response(url, status), allowed_urls=frozenset(allowed)
    )
    return items, evidence


# ── A: the citation is bound to the retrieved set ────────────────────────────


def test_a_retrieved_citation_survives():
    items, evidence = _read(RETRIEVED)
    assert items[0].source_url == RETRIEVED
    assert evidence[0]["url"] == RETRIEVED


def test_a_citation_that_was_never_retrieved_is_dropped():
    items, evidence = _read("https://attacker.example/never-retrieved")
    assert items[0].source_url == ""
    assert evidence == [], "an off-list evidence entry is still a citation"


def test_the_source_title_goes_with_an_off_list_url():
    """The title describes a page the reader is being sent to. Leaving it behind
    on a cleared URL reads as a citation whose link merely failed to render."""
    items, _ = _read("https://attacker.example/x")
    assert items[0].source_title == ""


def test_canonical_forms_still_match():
    """Scheme, www. and a trailing slash are the same page. A comparison on the
    raw string would drop legitimate citations and look like the model inventing
    them."""
    items, _ = _read("http://www.employer.example/about/")
    assert items[0].source_url == "http://www.employer.example/about/"


# ── B: the score is bound to the citation ─────────────────────────────────────


def test_an_unbacked_red_is_demoted_to_yellow():
    items, _ = _read("https://attacker.example/x", status="red")
    assert items[0].status == "yellow"


def test_a_backed_red_stays_red():
    items, _ = _read(RETRIEVED, status="red")
    assert items[0].status == "red"


def test_an_unbacked_green_loses_its_url_but_keeps_its_status():
    """A confirmed claim is not made less true by a missing link, and green
    already scores zero. Demoting it would invent a doubt."""
    items, _ = _read("https://attacker.example/x", status="green")
    assert items[0].status == "green"
    assert items[0].source_url == ""


def test_an_unbacked_yellow_is_left_alone():
    items, _ = _read("https://attacker.example/x", status="yellow")
    assert items[0].status == "yellow"
    assert items[0].source_url == ""


# ── the search found nothing at all ──────────────────────────────────────────


def test_when_nothing_was_retrieved_no_claim_is_refuted():
    """The search failing or returning empty is the common case, and it is the
    one that must not produce a `red`. An empty allowed set is what a failed
    search looks like from here."""
    items, evidence = _read(RETRIEVED, status="red", allowed=())
    assert items[0].status == "yellow"
    assert evidence == []


# ── the score, end to end ────────────────────────────────────────────────────


def test_a_demoted_item_adds_nothing_to_the_score():
    """The point of the demotion. `yellow` is already zero-weight, so this is
    the assertion that ties the parse fix to the number the reader acts on."""
    backed = [VerificationItem(label="Channel Match", status="red", explanation="x",
                               source_url=RETRIEVED)]
    unbacked = [VerificationItem(label="Channel Match", status="red", explanation="x",
                                 source_url="https://attacker.example/x")]

    assert _refutation_score_from_verify(backed) > 0
    assert _refutation_score_from_verify(unbacked) > 0, (
        "precondition: before binding, an uncited red already scores"
    )

    bound = [VerificationItem(label="Channel Match", status="yellow", explanation="x",
                              source_url="")]
    assert _refutation_score_from_verify(bound) is None


# ── the labeled-text fallback is bound too ───────────────────────────────────


def test_the_fallback_path_is_bound_as_well():
    """A model with no schema-capable endpoint answers in labeled text. If only
    the JSON path were bound, the fix would be bypassed by choosing a weaker
    model."""
    text = (
        "VERIFY: Channel Match\n"
        "STATUS: red\n"
        "FINDING: directs applicants to a personal account\n"
        "SOURCE: https://attacker.example/never-retrieved | About us\n"
        "END VERIFY\n"
    )
    items, _report, _rec, used_json, evidence, _level, _score = _read_verify_output(
        text, allowed_urls=frozenset({RETRIEVED})
    )
    assert used_json is False
    assert items, "the fallback parser should still produce the item"
    assert items[0].source_url == ""
    assert items[0].status == "yellow"
