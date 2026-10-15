"""A test that cannot run from a clean install is not a test.

`backend/requirements.txt` pinned `pytest` but not `pytest-asyncio`, while 85
tests across the suite carry `@pytest.mark.asyncio`. There is no
`pyproject.toml`, `pytest.ini`, `setup.cfg`, `tox.ini` or lockfile anywhere in the
repository to declare it either, and no CI workflow to install it.

The reason it was never noticed is that `pytest_asyncio` *was* installed in the
working venv — a hand-install that the shipped manifest does not record. So the
suite passed, and the marker-gated assertions (the input caps, the rate-limit
refusal, and two of the five that assert the offline provider guard) would have
been collected and never awaited by anyone building from the file.

pytest-asyncio defaults to strict mode, where the markers are load-bearing rather
than decorative, so the gap is not cosmetic: without the plugin those tests are
inert.

Asserted as a relationship rather than a literal, so the guard reads the markers
out of the suite instead of restating a count that could go stale.
"""

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REQUIREMENTS = BACKEND / "requirements.txt"
TESTS = BACKEND / "tests"

# Plugin package name as imported -> the distribution that provides it.
PLUGIN_FOR_MARKER = {"asyncio": "pytest-asyncio"}


def _requirements() -> str:
    return REQUIREMENTS.read_text(encoding="utf-8").lower()


def _marker_names() -> set[str]:
    names: set[str] = set()
    for path in sorted(TESTS.glob("*.py")):
        for match in re.finditer(r"@pytest\.mark\.(\w+)", path.read_text(encoding="utf-8")):
            names.add(match.group(1))
    return names


def test_the_asyncio_plugin_is_declared_where_the_markers_need_it():
    markers = _marker_names()
    assert "asyncio" in markers, (
        "the suite no longer marks async tests; pytest-asyncio can be dropped"
    )

    requirements = _requirements()
    missing = [
        distribution
        for marker, distribution in PLUGIN_FOR_MARKER.items()
        if marker in markers and distribution not in requirements
    ]
    assert not missing, (
        f"{missing} used by the suite but absent from requirements.txt, so a "
        "clean install collects the tests and never runs them"
    )


def test_the_plugin_is_pinned_rather_than_left_floating():
    """An unpinned test dependency turns a future suite run into a different
    suite run, which is the reproducibility problem this file exists to close."""
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        if line.lower().startswith("pytest-asyncio"):
            assert "==" in line, f"pytest-asyncio is not pinned: {line!r}"
            return
    raise AssertionError("pytest-asyncio is not declared at all")


# A general "every import is declared" check was written and removed. Deciding
# which imports are satisfied by a transitive dependency needs real resolution,
# and a hand-maintained stdlib allowlist is worse than nothing: it looks like the
# check is comprehensive while silently passing on any name someone forgot to add,
# and it grows a second list that drifts from the first. The marker check above
# covers the case that actually happened.
