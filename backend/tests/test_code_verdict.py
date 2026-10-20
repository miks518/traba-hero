"""The final level is code-owned, and the calculator is live again.

`risk_calculator` was retired on 2026-10-17 because it priced the *category* of a
finding instead of who was asking. The retirement put the level in the verification
model, which does hold the context. It also let the same model price a category:
a real employer using a Gmail address while its own site was `company.com.ph`
became a red Channel Match and "Do not proceed".

The response is a split, not a return to the old design. The model reports channel
facts; `channel_match.py` assigns that category's severity; `verdict.py` combines
the posting's findings with the refutation sum. The calculator's arithmetic is the
one place the weights live, so it is imported rather than reimplemented - and that
makes this file the guard that it stays wired.

The semantic tests the retirement introduced are still here, because they were
right and the reversal did not undo them:

  - a scan that has read a document and seen no evidence carries no level
  - a posting naming no employer carries no level
  - a response that was readable but carried nothing carries no level
"""

import ast
from pathlib import Path

from app.models.schemas import Anomaly, VerificationItem
from app.services.scanner.verdict import code_verdict

APP = Path(__file__).resolve().parents[1] / "app"
SCANNER = APP / "services" / "scanner"


def _imports_in(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            found.update(alias.name for alias in node.names)
    return found


def _calls_in(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    return {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def _channel(status: str = "red", escalation: str = "government") -> VerificationItem:
    return VerificationItem(
        label="Channel Match",
        status=status,
        explanation="The posting and the employer's results use different channels.",
        escalation=escalation,
    )


def _high(flag: str = "Asks for a fee") -> Anomaly:
    return Anomaly(flag=flag, reasoning="r", severity="high")


def _mid(flag: str = "Vague employer") -> Anomaly:
    return Anomaly(flag=flag, reasoning="r", severity="mid")


class TestTheCalculatorIsActuallyLive:
    def test_the_verdict_module_imports_the_live_arithmetic(self):
        imports = _imports_in(SCANNER / "verdict.py")

        assert {
            "_posting_risk_from_flags",
            "_combine_scores",
            "_level_for",
            "_refutation_score_from_verify",
        } <= imports

    def test_the_verification_flow_calls_the_code_verdict(self):
        """The flow is where the model's fields used to become the wire values.

        A `code_verdict` that exists but is never called would leave the old lane
        open, which is the half-wired state this project cares about most.
        """
        assert "code_verdict" in _calls_in(SCANNER / "verification_flow.py")

    def test_the_verify_schema_no_longer_asks_the_model_for_a_level(self):
        from app.services.scanner.verification_prompt import VERIFY_RESPONSE_SCHEMA

        properties = VERIFY_RESPONSE_SCHEMA["properties"]

        assert "risk_level" not in properties
        assert "risk_score" not in properties
        assert "channel_match" in properties
        assert "channel_match" in VERIFY_RESPONSE_SCHEMA["required"]

    def test_the_calculator_docstring_no_longer_claims_to_be_retired(self):
        """A live module whose first line says RETIRED is the lie this split
        exists to avoid, in the other direction.
        """
        doc = ast.get_docstring(
            ast.parse((SCANNER / "risk_calculator.py").read_text(encoding="utf-8"))
        ) or ""

        assert not doc.startswith("RETIRED")
        assert "Live again" in doc
        assert "who is asking" in doc


class TestUnassessedIsNotLow:
    """The behaviour that made retiring it worthwhile is still the behaviour.

    Each of these produced a number before, in a state where the reader knows
    least. `None` is the honest value and the frontend already has a rendering
    for it, so nothing needed inventing to get here.
    """

    def test_a_scan_response_carries_no_level(self):
        from app.models.schemas import Anomaly as ScanAnomaly
        from app.services.scanner import _scan_response

        res = _scan_response(
            {
                "valid": True,
                "anomalies": [
                    ScanAnomaly(
                        flag="Asks for a fee", reasoning="r", severity="high"
                    ).model_dump()
                ],
                "job_summary": "s",
            },
            "ACME",
        )
        assert res.risk_level is None, "a scan has seen no evidence and must claim no level"
        assert res.risk_score is None

    def test_the_schema_defaults_to_unassessed_rather_than_low(self):
        """The default is what a response with the field omitted gets. `low` as a
        default means every malformed or partial answer reads as reassuring."""
        from app.models.schemas import ScanResponse

        bare = ScanResponse(valid=True)
        assert bare.risk_level is None
        assert bare.risk_score is None


class TestTheCodeVerdict:
    def test_no_findings_and_no_refutation_is_low(self):
        score, level, breakdown = code_verdict([], [])

        assert (score, level) == (0, "low")
        assert breakdown["posting_score"] == 0
        assert breakdown["verification_score"] is None

    def test_one_high_posting_finding_is_moderate(self):
        score, level, _ = code_verdict([_high()], [])

        assert (score, level) == (40, "moderate")

    def test_one_mid_posting_finding_is_low(self):
        score, level, _ = code_verdict([_mid()], [])

        assert (score, level) == (12, "low")

    def test_two_high_posting_findings_are_critical(self):
        score, level, _ = code_verdict([_high(), _high("Sends documents elsewhere")], [])

        assert (score, level) == (80, "critical")

    def test_a_strong_channel_red_gets_a_high_floor(self):
        """One refuted Channel Match is 25 points, which is `low` on its own.

        That is right for "we could not confirm the channel" and wrong for "a
        government office sends applicants to a domain that is not its own." The
        floor moves it to the bottom of `high`; it does not make it critical.
        """
        score, level, breakdown = code_verdict([], [_channel()])

        assert (score, level) == (51, "high")
        assert breakdown["channel_floor"] is True
        assert breakdown["channel_escalation"] == "government"

    def test_a_lookalike_gets_the_same_floor(self):
        score, level, breakdown = code_verdict(
            [], [_channel(escalation="lookalike")]
        )

        assert (score, level) == (51, "high")
        assert breakdown["channel_escalation"] == "lookalike"

    def test_a_strong_channel_red_plus_one_high_finding_is_high_not_critical(self):
        """The floor does not decide the headline; the combined score does.

        40 + 25 = 65 is `high`. The most serious headline still needs 76, so one
        strong channel contradiction cannot claim it alone or with one fee.
        """
        score, level, _ = code_verdict([_high()], [_channel()])

        assert (score, level) == (65, "high")

    def test_a_strong_channel_red_plus_two_high_findings_is_critical(self):
        score, level, _ = code_verdict(
            [_high(), _high("Sends documents elsewhere")], [_channel()]
        )

        assert (score, level) == (100, "critical")

    def test_a_free_email_with_a_finding_is_red_but_not_floored(self):
        """The combination is the pattern, and the posting's finding carries its
        own weight. There is no extra 51-point floor for a phrase the scan
        already priced.
        """
        score, level, breakdown = code_verdict(
            [_high()], [_channel(escalation="free_email_with_findings")]
        )

        assert (score, level) == (65, "high")
        assert breakdown["channel_floor"] is False
        assert breakdown["channel_escalation"] == ""

    def test_a_free_email_alone_adds_nothing(self):
        score, level, breakdown = code_verdict(
            [], [_channel(status="yellow", escalation="free_email")]
        )

        assert (score, level) == (0, "low")
        assert breakdown["verification_score"] is None

    def test_a_green_channel_adds_nothing(self):
        score, level, breakdown = code_verdict(
            [], [_channel(status="green", escalation="match")]
        )

        assert (score, level) == (0, "low")
        assert breakdown["verification_score"] is None

    def test_a_red_item_outside_the_channel_rule_gets_no_floor(self):
        """A refuted Reputation claim is still worth its weight and nothing more.

        Only the two strong Channel Match rules carry the floor; a red card from
        another category must not borrow it.
        """
        reputation = VerificationItem(
            label="Reputation",
            status="red",
            explanation="A result contradicts the posting's claim.",
        )
        score, level, breakdown = code_verdict([], [reputation])

        # Reputation's refutation weight is 7; the point is that it is not 25 and
        # not floored, not that every red card is worth the same.
        assert (score, level) == (7, "low")
        assert breakdown["channel_floor"] is False

    def test_the_breakdown_names_code_as_the_level_source(self):
        _, _, breakdown = code_verdict([_high()], [])

        assert breakdown["level_source"] == "code"
        assert breakdown["sources"] == ["posting", "verification"]
        assert breakdown["risk_level"] == "moderate"

    def test_a_stale_assessment_removes_its_finding_from_the_posting_score(self):
        """The previous feature's point, kept after the level moved into code.

        A retrieved employer-specific source that accounts for a finding means
        the finding no longer stands. The model no longer writes the level, so
        the exclusion has to happen here; otherwise the stale card renders while
        its 40 points still drive the headline.
        """
        from app.models.schemas import AnomalyAssessment

        stale = AnomalyAssessment(
            index=1,
            status="stale",
            finding="The employer's own careers page states the exam fee.",
            source_title="Careers",
            source_url="https://example.ph/careers",
        )

        score, level, breakdown = code_verdict(
            [_high("Exam fee"), _high("Sends documents elsewhere")], [], [stale]
        )

        assert (score, level) == (40, "moderate")
        assert breakdown["stale_excluded"] == 1
        assert breakdown["high_count"] == 1

    def test_a_yellow_or_red_assessment_does_not_lower_the_posting_score(self):
        """Only `stale` accounts for a finding. Yellow is absence, and red is a
        contradiction, which is not a reason to stop counting the finding.
        """
        from app.models.schemas import AnomalyAssessment

        assessments = [
            AnomalyAssessment(index=1, status="yellow", finding="Not checked."),
            AnomalyAssessment(index=2, status="red", finding="A source contradicts it."),
        ]

        score, level, breakdown = code_verdict(
            [_high(), _high()], [], assessments
        )

        assert (score, level) == (80, "critical")
        assert breakdown["stale_excluded"] == 0
