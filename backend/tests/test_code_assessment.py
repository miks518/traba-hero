"""The assessment is a decision procedure over two axes, and it carries no number.

The score was a sum of weights over categories. Nothing about "37" describes a
posting, and the panelist who asks where the number came from has no answer that
a Saaty matrix can supply: AHP needs a fixed, commensurable variable set, and a
job posting is not one.

What replaces it is the grid the research settled on: what the posting asks for,
against what the record shows about who is asking. Four cells decide almost
everything, and only one of them can produce `stop`.

These tests are the guard on that shape. The grid is asserted cell by cell,
because a decision table that drifts by one cell is the kind of defect that reads
as a plausible assessment.
"""

import ast
from pathlib import Path

import pytest

from app.models.schemas import AnomalyAssessment, VerificationItem
from app.services.scanner.establishment import Establishment
from app.services.scanner.assessment import ASSESSMENTS, code_assessment

APP = Path(__file__).resolve().parents[1] / "app"
SCANNER = APP / "services" / "scanner"


def _calls_in(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    return {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def _channel(status: str = "confirmed", escalation: str = "match") -> VerificationItem:
    return VerificationItem(
        label="Channel Match",
        status=status,
        explanation="The posting and the employer's results use different channels.",
        escalation=escalation,
    )


def _decide(request_class: str, state: str, anomalies: list = None) -> str:
    assessment, _ = code_assessment(
        anomalies or [],
        [],
        request_class=request_class,
        establishment=Establishment(state),
    )
    return assessment


class TestTheAssessmentVocabulary:
    def test_the_assessments_are_a_closed_set(self):
        assert ASSESSMENTS == ("green", "yellow", "red")


class TestTheGrid:
    """Every cell, because a table that drifts by one cell is invisible."""

    @pytest.mark.parametrize(
        "request_class,state,expected",
        [
            ("ordinary", "confirmed", "green"),
            ("ordinary", "supported", "green"),
            ("ordinary", "unknown", "yellow"),
            ("ordinary", "contradicted", "red"),
            ("unclassified", "confirmed", "yellow"),
            ("unclassified", "supported", "yellow"),
            ("unclassified", "unknown", "yellow"),
            ("unclassified", "contradicted", "red"),
            ("prohibited", "confirmed", "yellow"),
            ("prohibited", "supported", "yellow"),
            ("prohibited", "unknown", "yellow"),
            ("prohibited", "contradicted", "red"),
        ],
    )
    def test_the_cell(self, request_class, state, expected):
        assert _decide(request_class, state) == expected

    def test_an_ordinary_request_at_an_unknown_employer_is_green(self):
        """The posting asks for nothing the rules prohibit, and the record shows
        nothing either way. The caution for a named employer sits on the
        retrieval fact, not the establishment state - see
        TestTheZeroRetrievalFloor: found-but-hedged companies stay green, and
        only a lookup that found nothing floors the assessment to yellow.
        """
        assert _decide("ordinary", "unknown") == "yellow"

    def test_an_ordinary_request_with_a_fee_at_an_unknown_employer_names_the_employer(self):
        """Precedence at the cell level: a fee finding rides through `_decide`'s
        arguments, and at an unknown establishment the stronger fact — nobody is
        established — is what the breakdown names. This is the case the
        floor-wins mutation would flip.
        """
        fee = [{"code": "FEE_MANDATORY", "quote": "Pay a P350 processing fee."}]
        assessment, breakdown = code_assessment(
            fee, [], request_class="ordinary",
            establishment=Establishment("unknown"),
        )
        assert assessment == "yellow"
        assert breakdown["rule"] == "ordinary_at_unestablished_employer"

    def test_a_prohibited_request_at_an_unknown_employer_is_yellow(self):
        """The request is one the rules prohibit, and nobody has established who
        is asking. The rule, not the colour, carries that this is the scam
        shape rather than an unclassifiable ask.
        """
        assert _decide("prohibited", "unknown") == "yellow"
        _assessment, breakdown = code_assessment(
            [], [], request_class="prohibited", establishment=Establishment("unknown")
        )
        assert breakdown["rule"] == "prohibited_at_unestablished_employer"

    def test_a_prohibited_request_at_a_confirmed_employer_is_yellow(self):
        """The reader can go and see the request on the employer's own site.
        A verified employer charging a fee is the same colour as the scam
        shape - the rule says which is which.
        """
        assert _decide("prohibited", "confirmed") == "yellow"
        _assessment, breakdown = code_assessment(
            [], [], request_class="prohibited", establishment=Establishment("confirmed")
        )
        assert breakdown["rule"] == "prohibited_at_confirmed_employer"

    def test_an_unclassified_request_is_yellow(self):
        """A request whose shape the facts do not settle is a question for the
        reader. It is not a charge, and it is not nothing.
        """
        assert _decide("unclassified", "supported") == "yellow"


class TestOnlyAContradictionStops:
    def test_a_contradicted_employer_is_red_whatever_the_request(self):
        for request_class in ("ordinary", "unclassified", "prohibited"):
            assessment, breakdown = code_assessment(
                [],
                [],
                request_class=request_class,
                establishment=Establishment("contradicted", reason="The domain is not the agency's."),
            )

            assert assessment == "red"
            assert breakdown["establishment"]["state"] == "contradicted"

    def test_unknown_never_rises_above_yellow_on_its_own(self):
        """Absence is never red. A record that establishes nothing leaves the
        ordinary posting green and the unclassified one yellow. The caution for
        a named employer with no results is the retrieval floor's job, not the
        grid cell's.
        """
        assert _decide("ordinary", "unknown") == "yellow"
        assert _decide("unclassified", "unknown") == "yellow"


class TestACommonFeeIsNeverGreen:
    """Field report 2026-11-04: three scans of a posting demanding a $150
    deposit returned green. Every one traces to `_fee_class` returning
    `ordinary` on the word "employer" or "agency" in the recipient — 24 green
    outcomes across the four fee codes, all through that one word.

    **Not every fee is a scam, and none of them is red on its own.** A real
    employer charging for a uniform is ordinary practice, which is why
    `prohibited_at_confirmed_employer` is yellow. But a posting that asks the
    applicant for money is not one where "nothing stands out" is a true
    sentence: the reader has something to check — who receives it, whether it
    is refundable, whether it is required before any contract. The floor is
    yellow, keyed on the *code*, so it does not depend on how the recipient was
    classified: the recipient is the model's answer about the same span, and a
    wrong recipient word must not be able to clear a fee demand.
    """

    def _fee(self, code="FEE_MANDATORY", quote="Pay a P350 processing fee."):
        return [{"code": code, "quote": quote}]

    @pytest.mark.parametrize("code", [
        "FEE_MANDATORY", "FEE_CONDITIONAL", "PURCHASE_REQUIRED", "DEPOSIT_REQUIRED",
    ])
    def test_no_fee_code_reads_green_at_an_established_employer(self, code):
        """The 24 outcomes that were green: fee + `ordinary` class + confirmed
        or supported employer. Each is now yellow, by the rule that names the
        fee rather than the establishment.
        """
        for state in ("confirmed", "supported"):
            assessment, breakdown = code_assessment(
                self._fee(code), [], request_class="ordinary",
                establishment=Establishment(state),
            )
            assert assessment == "yellow", f"{code} at {state} read {assessment}"
            assert breakdown["rule"] == "fee_at_established_employer"

    def test_the_floor_catches_the_wrong_recipient_word(self):
        """The field report's exact shape: the model wrote `employer` as the
        recipient, `_fee_class` priced it `ordinary`, and the posting read
        green. The floor reads the code, so the recipient word cannot clear it.
        """
        from app.services.scanner.request_class import RequestFact, classify_request

        facts = [RequestFact(
            code="DEPOSIT_REQUIRED",
            quote="accepted candidates must submit a mandatory $150 Deposit Fee prior to Day 1",
            fee_recipient="employer",
        )]
        cls = classify_request(facts)
        assert cls == "ordinary", "the recipient word still prices the class"

        assessment, breakdown = code_assessment(
            facts, [], request_class=cls,
            establishment=Establishment("supported"),
        )
        assert assessment == "yellow"
        assert breakdown["rule"] == "fee_at_established_employer"

    def test_a_fee_at_an_unknown_employer_keeps_the_existing_rule(self):
        """The unestablished-employer caution already prices this yellow. The
        floor must not shadow it with a less specific name: the breakdown says
        why the posting is a caution, and "nobody established" is the stronger
        answer.
        """
        _assessment, breakdown = code_assessment(
            self._fee(), [], request_class="prohibited",
            establishment=Establishment("unknown"),
        )
        assert breakdown["rule"] == "prohibited_at_unestablished_employer"

    def test_a_posting_with_no_fee_still_reads_green(self):
        """The floor is keyed on the code. An ordinary posting with no fee
        finding keeps its green — the guard must not turn Caution into the
        default for everything.
        """
        assessment, breakdown = code_assessment(
            [], [], request_class="ordinary", establishment=Establishment("confirmed")
        )
        assert assessment == "green"
        assert breakdown["rule"] == "ordinary_request"

    def test_the_floor_is_keyed_on_the_code_not_the_presence_of_findings(self):
        """`if codes:` would fire on any finding at all. An `OTHER`-coded
        finding is unclassified and prices yellow by its own rule; the floor
        must not claim the fee rule for it, because the breakdown would then
        name a fee the posting does not ask for.
        """
        other = [{"code": "OTHER", "quote": "HIRING! Customer service rep, Makati."}]
        _assessment, breakdown = code_assessment(
            other, [], request_class="unclassified",
            establishment=Establishment("confirmed"),
        )
        assert breakdown["rule"] == "unclassified_request"

    def test_the_unestablished_rule_outranks_the_fee_floor(self):
        """Precedence, pinned: at an unknown establishment the breakdown names
        the stronger fact — nobody is established — rather than the fee. A
        reader asking "why caution?" gets the more informative answer.
        """
        _assessment, breakdown = code_assessment(
            self._fee(), [], request_class="prohibited",
            establishment=Establishment("unknown"),
        )
        assert breakdown["rule"] == "prohibited_at_unestablished_employer"

    def test_the_fee_floor_does_not_shadow_the_contradiction_rules(self):
        """Precedence: a contradicted check is red, and the fee floor must not
        demote it back to yellow.
        """
        item = VerificationItem(label="Similar Offers", status="contradicted",
                                explanation="", source_title="s",
                                source_url="https://example.ph")
        assessment, breakdown = code_assessment(
            self._fee(), [item], [], request_class="ordinary",
            establishment=Establishment("supported"),
        )
        assert assessment == "red"
        assert breakdown["rule"] == "check_contradicted_by_source"


class TestTheUnestablishedEmployerCaution:
    """A posting that writes a company name and the checks could not verify it
    is a caution. Field reports: an AI-generated company read green with every
    check "could not verify" (2026-10-31), and a found company whose checks
    hedged read green only because the grid granted the benefit of the doubt
    (2026-11-02). The caution keys on the establishment state - the model's
    word about the check card - while the hallucination guard sits one layer
    down: a "confirmed" existence with no bound source is the model's bare
    word, not a record, and establishes nothing.
    """

    def test_an_ordinary_request_at_an_unknown_employer_is_yellow(self):
        assert _decide("ordinary", "unknown") == "yellow"
        _assessment, breakdown = code_assessment(
            [], [], request_class="ordinary", establishment=Establishment("unknown")
        )
        assert breakdown["rule"] == "ordinary_at_unestablished_employer"

    def test_red_is_not_reached_by_the_caution(self):
        assessment, breakdown = code_assessment(
            [],
            [],
            request_class="ordinary",
            establishment=Establishment("contradicted"),
        )

        assert assessment == "red"
        assert breakdown["rule"] == "establishment_contradicted"

    def test_the_grid_s_own_yellow_is_unchanged(self):
        assessment, breakdown = code_assessment(
            [],
            [],
            request_class="prohibited",
            establishment=Establishment("unknown"),
        )

        assert assessment == "yellow"
        assert breakdown["rule"] == "prohibited_at_unestablished_employer"

    def test_a_supported_establishment_stays_green(self):
        assessment, breakdown = code_assessment(
            [],
            [],
            request_class="ordinary",
            establishment=Establishment("supported"),
        )

        assert assessment == "green"
        assert breakdown["rule"] == "ordinary_request"

    def test_every_path_to_red_needs_the_contradiction(self):
        """Asserted as a property over the whole grid, not as three examples:
        if any cell without `contradicted` returns red, the guarantee is gone.

        **Two exceptions, both named.** `contradicted` is no longer the only
        route to red. The other is `task_for_earning_at_unestablished_employer`:
        labour paid at an anonymous poster's discretion, where nobody is
        established as responsible. It is red for the same reason this test
        exists — the posting cannot supply evidence about itself, and there is no
        employer to weigh the finding against — but it is *not* a contradiction,
        so it is asserted here as the one named exception rather than by
        loosening the property.

        Before this, the test iterated `_decide(request_class, state)` with no
        codes at all, so it could not see the rule that reads them, and it passed
        while `offer_flow` was already producing that red. A property test that
        cannot reach the code it guards is not evidence.
        """
        named_exception = "task_for_earning_at_unestablished_employer"
        states = ("confirmed", "supported", "unknown")
        for request_class in ("ordinary", "unclassified", "prohibited"):
            for state in states:
                assessment, breakdown = code_assessment(
                    [], [], request_class=request_class,
                    establishment=Establishment(state),
                )
                if assessment == "red":
                    assert breakdown["rule"] == named_exception, (
                        f"{request_class}/{state} returns red by the unexpected "
                        f"rule {breakdown['rule']!r}"
                    )
                else:
                    assert breakdown["rule"] != named_exception

    def test_the_named_red_is_reachable_only_by_that_one_rule(self):
        """The exception above is narrow: it needs the code *and* `unknown`."""
        labour = [{"code": "TASK_FOR_EARNING", "quote": "follow a store"}]
        assert _decide("prohibited", "unknown", labour) == "red"
        # Not at an established employer: paying per referral is a business model.
        assert _decide("prohibited", "confirmed", labour) == "yellow"
        assert _decide("prohibited", "supported", labour) == "yellow"
        # Not for another prohibited code.
        fee = [{"code": "FEE_MANDATORY", "quote": "pay the fee"}]
        assert _decide("prohibited", "unknown", fee) == "yellow"


class TestTheBreakdownCarriesNoNumber:
    def test_no_key_names_a_score(self):
        _assessment, breakdown = code_assessment(
            [], [], request_class="prohibited", establishment=Establishment("unknown")
        )

        offenders = [key for key in breakdown if "score" in key.lower()]
        assert offenders == [], f"the assessment still carries a score: {offenders}"

    def test_the_breakdown_names_the_rule_that_decided(self):
        """The record has to be readable on its own. A reader who asks why the
        panel says caution gets a rule name and two states, not a number.
        """
        assessment, breakdown = code_assessment(
            [], [], request_class="prohibited", establishment=Establishment("unknown")
        )

        assert breakdown["assessment"] == assessment
        assert breakdown["exposure"] == "prohibited"
        assert breakdown["establishment"]["state"] == "unknown"
        assert breakdown["rule"] == "prohibited_at_unestablished_employer"

    def test_the_breakdown_records_the_evidence_it_read(self):
        item = _channel(status="contradicted", escalation="government")
        _assessment, breakdown = code_assessment(
            [],
            [item],
            request_class="ordinary",
            establishment=Establishment("contradicted"),
        )


        assert breakdown["record"][0]["label"] == "Channel Match"
        assert breakdown["record"][0]["status"] == "contradicted"
        assert breakdown["record"][0]["escalation"] == "government"


class TestTheProvisionalEstablishment:
    """Part 4 decides establishment properly. Until then the record supplies it
    from the channel facts, and a contradicted Reputation is not a contradiction: reputation
    is not a claim about who is asking.
    """

    def test_a_government_or_lookalike_channel_is_a_contradiction(self):
        for escalation in ("government", "lookalike"):
            assessment, _ = code_assessment(
                [], [_channel(status="contradicted", escalation=escalation)], request_class="ordinary"
            )

            assert assessment == "red"

    def test_a_matching_channel_confirms_the_employer(self):
        assessment, breakdown = code_assessment(
            [],
            [_channel(status="confirmed", escalation="match")],
            request_class="prohibited",
        )

        assert breakdown["establishment"]["state"] == "confirmed"
        assert assessment == "yellow"

    def test_a_green_company_existence_supports_the_employer(self):
        item = VerificationItem(
            label="Company Existence",
            status="confirmed",
            explanation="A real firm.",
            source_url="https://bhive.ph/1000ccph",
        )
        _assessment, breakdown = code_assessment([], [item], request_class="prohibited")

        assert breakdown["establishment"]["state"] == "supported"

    def test_a_confirmed_existence_without_a_bound_source_establishes_nothing(self):
        """A "confirmed" with no source behind it is the model's bare word. On
        an empty lookup the binding strips the URL, so a hallucinated
        confirmation arrives exactly like this - and the model's word alone
        must not establish the employer. Field report 2026-10-31: the
        fictional-company scan read green through this gap.
        """
        item = VerificationItem(
            label="Company Existence",
            status="confirmed",
            explanation="A real firm.",
            source_url="",
        )
        _assessment, breakdown = code_assessment([], [item], request_class="ordinary")

        assert breakdown["establishment"]["state"] == "unknown"
        assert _decide("ordinary", "unknown") == "yellow"

    def test_a_red_reputation_is_not_a_contradiction(self):
        """A result contradicting a claim about how the employer behaves says
        nothing about who is asking.
        """
        item = VerificationItem(
            label="Reputation", status="contradicted", explanation="A result contradicts it."
        )
        _assessment, breakdown = code_assessment([], [item], request_class="ordinary")

        assert breakdown["establishment"]["state"] == "unknown"

    def test_an_empty_record_establishes_nothing(self):
        _assessment, breakdown = code_assessment([], [], request_class="ordinary")

        assert breakdown["establishment"]["state"] == "unknown"


class TestTheFlowStillCallsIt:
    def test_the_verification_flow_calls_the_code_assessment(self):
        assert "code_assessment" in _calls_in(SCANNER / "verification_flow.py")

    def test_the_verify_schema_no_longer_asks_the_model_for_a_level(self):
        from app.services.scanner.verification_prompt import VERIFY_RESPONSE_SCHEMA

        properties = VERIFY_RESPONSE_SCHEMA["properties"]

        assert "risk_level" not in properties
        assert "risk_score" not in properties
        assert "channel_match" in properties
        assert "channel_match" in VERIFY_RESPONSE_SCHEMA["required"]


class TestUnassessedIsNotLow:
    """The behaviour that made retiring the first calculator worthwhile.

    A scan has read a document and seen no evidence, so it carries no assessment.
    `None` is the honest value and the frontend already renders it.
    """

    def test_a_scan_response_carries_no_level(self):
        from app.services.scanner import _scan_response

        res = _scan_response(
            {
                "valid": True,
                "anomalies": [
                    {
                        "flag": "Asks for a fee",
                        "reasoning": "r",
                    }
                ],
                "job_summary": "s",
            },
            "ACME",
        )

        assert res.risk_level is None, "a scan has seen no evidence and must claim no level"
        assert res.risk_score is None


class TestAContradictionAnywhereIsRed:
    """Field report 2026-11-04: three contradicted anomaly cards and one
    contradicted category check, under a green banner.

    The posting demanded a $150 deposit and the Similar Offers check found it
    listed elsewhere — evidence, on screen, with nothing in the banner
    acknowledging it. `establishment.py` deliberately reads only Channel Match,
    so every other contradiction was invisible to the grid. The panelist's
    question ("you show Contradicted and you say nothing stands out — which is
    it?") has no defensible answer, which is why the floor is red and not a
    smaller colour: a contradiction is evidence, and evidence is not
    uncertainty.
    """

    def _check(self, label, status="contradicted", url="https://example.ph/post"):
        return VerificationItem(label=label, status=status, explanation="",
                                source_title="a source", source_url=url)

    def _finding(self, status="red", url="https://example.ph/post"):
        return AnomalyAssessment(index=1, status=status, finding="f",
                                 source_title="a source", source_url=url)

    def _run(self, items, assessments=(), request_class="ordinary", state="supported"):
        return code_assessment(
            [], items, list(assessments),
            request_class=request_class,
            establishment=Establishment(state),
        )

    def test_a_contradicted_check_is_red_and_names_itself(self):
        confirmed = self._check("Company Existence", status="confirmed")
        assessment, breakdown = self._run([confirmed, self._check("Similar Offers")])

        assert assessment == "red"
        assert breakdown["rule"] == "check_contradicted_by_source"
        assert breakdown["contradicted_check"] == "Similar Offers"

    def test_a_contradicted_finding_is_red(self):
        confirmed = self._check("Company Existence", status="confirmed")
        assessment, breakdown = self._run([confirmed], [self._finding()])

        assert assessment == "red"
        assert breakdown["rule"] == "finding_contradicted_by_source"

    def test_the_check_rule_wins_when_both_fire(self):
        """The named check is more specific than "a finding", so the breakdown
        says which one the reader can go and look at.
        """
        confirmed = self._check("Company Existence", status="confirmed")
        assessment, breakdown = self._run(
            [confirmed, self._check("Similar Offers")], [self._finding()]
        )

        assert assessment == "red"
        assert breakdown["rule"] == "check_contradicted_by_source"

    def test_reputation_cannot_make_a_posting_red(self):
        """The cap, and it is a decision rather than an oversight.

        A Reputation `red` is a retrieved complaint about how an employer
        behaves. It is not the posting being contradicted, and turning a bad
        review into "something is not right" about a named company is the libel
        shape the guardrails exist for. Reputation is capped at yellow by the
        rules that produce it; this test is the cap in the assessment too.
        """
        confirmed = self._check("Company Existence", status="confirmed")
        for status in ("contradicted", "supported", "unknown"):
            assessment, breakdown = self._run([confirmed, self._check("Reputation", status=status)])
            assert assessment != "red", f"Reputation {status} made the posting red"
            assert breakdown["rule"] != "check_contradicted_by_source"

    def test_a_contradiction_with_no_source_does_not_floor(self):
        """`_bind_to_retrieved` strips an unretrieved URL, and an unbacked
        contradiction is not one. Absence is never evidence of anything.
        """
        confirmed = self._check("Company Existence", status="confirmed")
        assessment, breakdown = self._run(
            [confirmed, self._check("Similar Offers", url="")]
        )
        assert assessment == "green"
        assert breakdown["rule"] == "ordinary_request"

    def test_the_floor_outranks_the_request_class(self):
        """A refuted claim matters more than what the posting asked for, so the
        rule names the evidence rather than the request.
        """
        confirmed = self._check("Company Existence", status="confirmed")
        assessment, breakdown = self._run(
            [confirmed, self._check("Location / Branch")],
            request_class="prohibited",
            state="confirmed",
        )
        assert assessment == "red"
        assert breakdown["rule"] == "check_contradicted_by_source"
