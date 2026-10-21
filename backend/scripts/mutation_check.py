"""Mutation check for the adaptive search controls.

A test that has never failed is not evidence. Each mutation below breaks exactly
one control; every one must turn at least one test red. Anything that survives
was not being tested, which is the finding this script exists to produce.

Run from backend/:  python scripts/mutation_check.py
Restores every file it touches, pass or fail.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (label, relative path, original, replacement, tests that must go red)
MUTATIONS = [
    (
        "the flag accepts an unrecognised mode",
        "app/config.py",
        'return value if value in _VALID_SEARCH_MODES else "fixed"',
        'return value if value in _VALID_SEARCH_MODES else "adaptive"',
        "tests/test_adaptive_search.py::TestTheFlag",
    ),
    (
        "a failed Round 1 still plans follow-ups",
        "app/services/scanner/search_planner.py",
        "    if not round1_ok:\n        return []",
        "    if False:\n        return []",
        "tests/test_search_planner.py::TestPlanner tests/test_adaptive_search.py::TestAdaptiveMode",
    ),
    (
        "row 1 requires the shared address again",
        "app/services/scanner/search_planner.py",
        "    if entity.names_differ and signals.main_domain:",
        "    if entity.names_differ and entity.shares_identifier and signals.main_domain:",
        "tests/test_search_planner.py::TestPlanner::test_the_live_case_spends_a_credit_on_the_posters_own_domain",
    ),
    (
        "the credit ceiling is removed",
        "app/services/scanner/search_planner.py",
        "        if len(planned) >= MAX_FOLLOWUPS:\n            return planned",
        "        if False:\n            return planned",
        "tests/test_search_planner.py::TestPlanner",
    ),
    (
        "conclusion words are allowed back into a query",
        "app/services/scanner/search_planner.py",
        "    return not any(term in words for term in _BANNED_QUERY_TERMS)",
        "    return True",
        "tests/test_search_planner.py::TestSafety tests/test_adaptive_search.py",
    ),
    (
        "every result claims to describe the entity",
        "app/services/scanner/search_planner.py",
        "            describes_entity=_mentions(body, entity_tokens) if entity.name else False,",
        "            describes_entity=True,",
        "tests/test_search_planner.py::TestLabelling",
    ),
    (
        "the scope filters instead of boosting",
        "app/services/search.py",
        'body["include_domains_mode"] = "prefer"',
        'body["include_domains_mode"] = "restrict"',
        "tests/test_multi_query.py::TestTheDomainScopeIsAPreferenceNotAFilter",
    ),
    (
        "a scope is taken from the posting's own text",
        "app/services/scanner/search_planner.py",
        "            include_domains=tuple(row.include_domains) if row.include_domains and entity.domain else (),",
        "                include_domains=(signals.main_domain,) if signals.main_domain else (),",
        "tests/test_search_planner.py::TestSafety tests/test_adaptive_search.py",
    ),
    (
        "model queries take priority over the planner",
        "app/services/scanner/search_planner.py",
        "    planned: list = []\n    for row in _planner_rows(signals, entity):",
        "    planned: list = []\n    for row in list(model_queries or []) + list(_planner_rows(signals, entity)):",
        "tests/test_search_planner.py::TestPlanner",
    ),
    (
        "the entity is never named in the prompt",
        "app/services/scanner/verification_flow.py",
        "            entity_name = entity.name",
        "            entity_name = \"\"",
        "tests/test_adaptive_search.py::TestLabellingReachesTheModel",
    ),
    (
        "fixed mode passes a second positional to search()",
        "app/services/scanner/verification_flow.py",
        "    return await asyncio.to_thread(runtime.get_search(), query)",
        "    return await asyncio.to_thread(runtime.get_search(), query, None)",
        "tests/test_adaptive_search.py::TestFixedModeIsUnchanged",
    ),
]


def _run(tests: str) -> bool:
    """True when the suite went red. Offline throughout: nothing is dialled."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *tests.split(), "-q", "--no-header", "-p", "no:randomly"],
        cwd=ROOT, capture_output=True, text=True,
    )
    return proc.returncode != 0


def main() -> int:
    survivors = []
    for label, relative, original, replacement, tests in MUTATIONS:
        path = ROOT / relative
        source = path.read_text(encoding="utf-8")
        if original not in source:
            print(f"SKIP  {label}: anchor not found in {relative}")
            survivors.append(f"{label} (anchor not found)")
            continue
        backup = tempfile.NamedTemporaryFile(delete=False, suffix=".bak")
        backup.write(source.encode("utf-8"))
        backup.close()
        try:
            path.write_text(source.replace(original, replacement, 1), encoding="utf-8")
            if _run(tests):
                print(f"caught  {label}")
            else:
                print(f"SURVIVED  {label}  -> {tests}")
                survivors.append(label)
        finally:
            shutil.copyfile(backup.name, path)
            Path(backup.name).unlink()

    print()
    if survivors:
        print(f"{len(survivors)} mutation(s) survived: {survivors}")
        return 1
    print(f"all {len(MUTATIONS)} mutations caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())