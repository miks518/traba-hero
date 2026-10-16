"""`risk_calculator` is retired, and this proves it rather than asserting it.

The project's standing rule is that code nothing calls is deleted, not left
behind, because a module that looks live and has thirty passing tests is the
most convincing kind of lie in a codebase. `risk_calculator.py` is the one
documented exception, kept because its Saaty derivation is a defensible artefact
and re-deriving it costs an afternoon.

That exception is only safe while it is genuinely unused. These tests read every
module under `app/` and check what it imports, which is the only way to catch the
failure mode that matters: someone reaching for a function that still works, and
half-wiring it back into the path. If any of these fail, the file is not dormant,
it is in use, and the module docstring is lying.

The second class of test is the semantic one. Retiring the calculator changed what
`None` means in three places, and each was a place where a *confident default*
was doing real damage:

  - a scan that has read a document and seen no evidence carries no level
  - a posting naming no employer carries no level
  - a response that was readable but carried nothing carries no level

All three used to produce a number, and all three are cases where the reader
knows least.
"""

import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
CALCULATOR = APP / "services" / "scanner" / "risk_calculator.py"

# The functions the retired module exports and nothing should be calling.
RETIRED = {
    "_posting_risk_from_flags",
    "_combine_scores",
    "_calculate_risk_score_from_verify",
}

# `_refutation_score_from_verify` is deliberately absent: the breakdown still
# records how much refuted evidence was seen, so it is genuinely live. It feeds a
# reporting field, not a level.


def _imports_in(path: Path) -> set[str]:
    """Names this module imports, from the `from X import a, b` form only.

    Read as `utf-8-sig`: a BOM on any file under `app/` is a real defect worth
    knowing about, but it should not be the reason this test errors before it can
    report anything. `test_scan_prompt_file.py` already guards the one BOM that
    has bitten this project, in a prompt file; a new one elsewhere would take
    this whole check down silently.
    """
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            found.update(alias.name for alias in node.names)
    return found


class TestTheCalculatorIsActuallyRetired:
    def test_nothing_outside_the_module_imports_a_retired_function(self):
        offenders = []
        for path in APP.rglob("*.py"):
            if path == CALCULATOR:
                continue
            leaked = _imports_in(path) & RETIRED
            if leaked:
                offenders.append(f"{path.relative_to(APP)} imports {sorted(leaked)}")
        assert not offenders, "retired calculator is still wired in: " + "; ".join(offenders)

    def test_the_module_says_so_at_the_top_rather_than_in_a_comment(self):
        """A retirement note in the middle of a 250-line file is a retirement note
        nobody reads. The docstring is what `help()` and every reader show first."""
        doc = ast.get_docstring(ast.parse(CALCULATOR.read_text(encoding="utf-8"))) or ""
        assert doc.startswith("RETIRED"), "the module docstring must lead with RETIRED"
        assert "test_risk_calculator_is_retired" in doc, (
            "the docstring should name the test that keeps the claim honest"
        )

    def test_it_documents_why_the_method_does_not_apply(self):
        """A retirement with no reason is a deletion someone will undo."""
        doc = (CALCULATOR.read_text(encoding="utf-8")).lower()
        assert "commensurable" in doc
        assert "who is asking" in doc or "who is asking," in doc


class TestUnassessedIsNotLow:
    """The behaviour that made retiring it worthwhile.

    Each of these produced a number before, in a state where the reader knows
    least. `None` is the honest value and the frontend already has a rendering
    for it, so nothing needed inventing to get here.
    """

    def test_a_scan_response_carries_no_level(self):
        from app.services.scanner import _scan_response
        from app.models.schemas import Anomaly

        res = _scan_response(
            {
                "valid": True,
                "anomalies": [
                    Anomaly(flag="Asks for a fee", reasoning="r", severity="high").model_dump()
                ],
                "job_summary": "s",
            },
            "ACME",
        )
        # Two high-severity indicators used to be 80 out of 100 and "high",
        # produced by a stage that had not looked anything up.
        assert res.risk_level is None, "a scan has seen no evidence and must claim no level"
        assert res.risk_score is None

    def test_the_schema_defaults_to_unassessed_rather_than_low(self):
        """The default is what a response with the field omitted gets. `low` as a
        default means every malformed or partial answer reads as reassuring."""
        from app.models.schemas import ScanResponse

        bare = ScanResponse(valid=True)
        assert bare.risk_level is None
        assert bare.risk_score is None
