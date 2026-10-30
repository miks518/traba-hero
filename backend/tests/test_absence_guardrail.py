"""The absence guardrail: a finding that names silence is not a finding.

The scan prompt forbids flagging the absence of something, but the rule
was prompt-only. A live scan reported "Pay Information not provided, the
posting states no pay amount or period" with no CODE line, and the empty
code rode `_class_for`'s deliberate catch-all into `unclassified`, which
the grid prices yellow — a hallucinated absence charged a clean posting a
Caution verdict while the summary said nothing was wrong.

The guardrail drops an absence-shaped label at `scan_result._anomalies`,
the last gate before the wire. See `docs/decisions/absence-guardrail.md`.
"""

from app.services.scanner.scan_result import _anomalies, _scan_response


def _anomaly(flag, code="", reasoning=""):
    return {"flag": flag, "code": code, "reasoning": reasoning}


class TestAbsenceGuardrail:
    def test_the_reported_finding_vanishes(self):
        """The report's exact finding is dropped, not normalised or stored."""
        out = _anomalies([
            _anomaly(
                "Pay Information not provided",
                reasoning="the posting states no pay amount or period",
            ),
        ])
        assert out == []

    def test_request_class_stays_ordinary(self):
        """Without the hallucinated finding, the posting prices green.

        This is the end of the chain that turned the hallucination into
        a Caution: `_scan_response` classifies from the findings it
        keeps, and a clean list must classify ordinary.
        """
        result = {
            "valid": True,
            "anomalies": [
                _anomaly(
                    "Pay Information not provided",
                    reasoning="the posting states no pay amount or period",
                )
            ],
            "attributes": {},
        }
        resp = _scan_response(result)
        assert resp.anomalies == []
        assert resp.request_class == "ordinary"

    def test_no_code_is_not_required_for_the_drop(self):
        """The guard reads the label, not the code.

        `normalise_code` returns "" for an absent code and OTHER for an
        unrecognised one; both rides the catch-all into `unclassified`.
        The drop must fire on the absence-shaped label either way.
        """
        assert _anomalies([_anomaly("No salary stated", code="")]) == []
        assert _anomalies([_anomaly("No salary stated", code="OTHER")]) == []
        assert _anomalies([_anomaly("Does not mention a work schedule", code="")]) == []

    def test_a_real_finding_survives(self):
        """A label naming something the posting does is kept whole."""
        real = _anomaly(
            "Asks applicants to pay a processing fee",
            code="FEE_MANDATORY",
            reasoning="The posting asks applicants to pay a fee before starting work",
        )
        out = _anomalies([real])
        assert len(out) == 1
        assert out[0].flag == "Asks applicants to pay a processing fee"
        assert out[0].code == "FEE_MANDATORY"

    def test_absence_phrasing_in_reasoning_only_is_kept(self):
        """The guard reads the label only.

        A real finding whose reasoning paraphrases absence — a shortened
        link whose destination the reasoning notes is not shown — must
        survive, or the guard eats genuine anomalies.
        """
        real = _anomaly(
            "Directs applicants to a shortened link",
            code="OTHER",
            reasoning="the link's destination is not shown",
        )
        out = _anomalies([real])
        assert len(out) == 1

    def test_mixed_list_keeps_the_real_and_drops_the_hallucinated(self):
        """One hallucination must not take real findings with it."""
        out = _anomalies([
            _anomaly(
                "Pay Information not provided",
                reasoning="the posting states no pay amount or period",
            ),
            _anomaly(
                "Asks applicants to pay a processing fee",
                code="FEE_MANDATORY",
            ),
        ])
        assert len(out) == 1
        assert out[0].flag == "Asks applicants to pay a processing fee"

    def test_empty_list_is_unchanged(self):
        assert _anomalies([]) == []
