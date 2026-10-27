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

from app.models.schemas import VerificationItem
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


def _decide(request_class: str, state: str) -> str:
    assessment, _ = code_assessment(
        [], [], request_class=request_class, establishment=Establishment(state)
    )
    return assessment


class TestTheAssessmentVocabulary:
    def test_the_assessments_are_a_closed_set(self):
        assert ASSESSMENTS == ("clear", "note", "caution", "stop")


class TestTheGrid:
    """Every cell, because a table that drifts by one cell is invisible."""

    @pytest.mark.parametrize(
        "request_class,state,expected",
        [
            ("ordinary", "confirmed", "clear"),
            ("ordinary", "supported", "clear"),
            ("ordinary", "unknown", "clear"),
            ("ordinary", "contradicted", "stop"),
            ("unclassified", "confirmed", "note"),
            ("unclassified", "supported", "note"),
            ("unclassified", "unknown", "note"),
            ("unclassified", "contradicted", "stop"),
            ("prohibited", "confirmed", "note"),
            ("prohibited", "supported", "caution"),
            ("prohibited", "unknown", "caution"),
            ("prohibited", "contradicted", "stop"),
        ],
    )
    def test_the_cell(self, request_class, state, expected):
        assert _decide(request_class, state) == expected

    def test_an_ordinary_request_at_an_unknown_employer_is_clear(self):
        """The posting asks for nothing the rules prohibit, and the record shows
        nothing either way. There is no finding to report and no limit to state.
        """
        assert _decide("ordinary", "unknown") == "clear"

    def test_a_prohibited_request_at_an_unknown_employer_is_caution(self):
        """The request is one the rules prohibit, and nobody has established who
        is asking. That is a warning, not a assessment.
        """
        assert _decide("prohibited", "unknown") == "caution"

    def test_a_prohibited_request_at_a_confirmed_employer_is_a_note(self):
        """The reader can go and see the request on the employer's own site.
        A verified employer charging a lawful fee is a note, not a caution.
        """
        assert _decide("prohibited", "confirmed") == "note"

    def test_an_unclassified_request_is_a_note(self):
        """A request whose shape the facts do not settle is a question for the
        reader. It is not a charge, and it is not nothing.
        """
        assert _decide("unclassified", "supported") == "note"


class TestOnlyAContradictionStops:
    def test_a_contradicted_employer_stops_whatever_the_request(self):
        for request_class in ("ordinary", "unclassified", "prohibited"):
            assessment, breakdown = code_assessment(
                [],
                [],
                request_class=request_class,
                establishment=Establishment("contradicted", reason="The domain is not the agency's."),
            )

            assert assessment == "stop"
            assert breakdown["establishment"]["state"] == "contradicted"

    def test_unknown_never_rises_above_a_note_on_its_own(self):
        """Absence is never red. A record that establishes nothing leaves the
        ordinary posting clear and the unclassified one a note.
        """
        assert _decide("ordinary", "unknown") == "clear"
        assert _decide("unclassified", "unknown") == "note"

    def test_every_path_to_stop_needs_the_contradiction(self):
        """Asserted as a property over the whole grid, not as three examples:
        if any cell without `contradicted` returns stop, the guarantee is gone.
        """
        states = ("confirmed", "supported", "unknown")
        for request_class in ("ordinary", "unclassified", "prohibited"):
            for state in states:
                assert _decide(request_class, state) != "stop"


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

            assert assessment == "stop"

    def test_a_matching_channel_confirms_the_employer(self):
        assessment, breakdown = code_assessment(
            [],
            [_channel(status="confirmed", escalation="match")],
            request_class="prohibited",
        )

        assert breakdown["establishment"]["state"] == "confirmed"
        assert assessment == "note"

    def test_a_green_company_existence_supports_the_employer(self):
        item = VerificationItem(
            label="Company Existence", status="confirmed", explanation="A real firm."
        )
        _assessment, breakdown = code_assessment([], [item], request_class="prohibited")

        assert breakdown["establishment"]["state"] == "supported"

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
