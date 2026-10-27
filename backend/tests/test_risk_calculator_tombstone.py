"""Tombstone for test_risk_model.py.

The AHP-derived weights and the two-stage risk model they powered are deleted.
`risk_calculator.py` and `docs/scoring.md` went with them. The assessment is a
decision procedure over two axes (what the posting asks for vs. what the record
shows about who is asking), not a sum of weights. `scripts/derive_refutation_weights.py`
is also deleted.

A test that recomputed the AHP matrix had no reason to exist once the weights
were no longer used. Leaving the test would have kept a passing assertion about
a derivation nobody reads any more.
"""

import importlib.util


def test_risk_calculator_module_is_deleted():
    assert importlib.util.find_spec("app.services.scanner.risk_calculator") is None


def test_derive_refutation_weights_script_is_deleted():
    from pathlib import Path
    script = Path(__file__).resolve().parents[1] / "scripts" / "derive_refutation_weights.py"
    assert not script.exists(), "scripts/derive_refutation_weights.py was deleted with the scoring model"