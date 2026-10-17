"""Regenerate `_FALLBACK_VERIFY_PROMPT` from VERIFY_PROMPT.md, byte for byte.

`test_the_fallback_is_a_copy_of_the_file_and_not_an_older_revision` asserts the
two are equal, which is the right guarantee: the fallback is what a deployment
with no VERIFY_PROMPT.md serves, and a hand-maintained second copy drifts.

Done in Python rather than PowerShell because a Set-Content round-trip has
already dropped a character from a source file in this repo.

Run from backend/:  python scripts/sync_verify_fallback.py
"""

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
PROMPT_FILE = BACKEND / "VERIFY_PROMPT.md"
TARGET = BACKEND / "app" / "services" / "scanner" / "verification_prompt.py"

text = PROMPT_FILE.read_text(encoding="utf-8").strip()

if "{" in text or "}" in text:
    raise SystemExit(
        "VERIFY_PROMPT.md contains braces. The fallback is an f-string, so "
        "inlining the file would make Python try to interpolate them. Either "
        "escape them in the file or drop the f prefix on the constant."
    )

# `"""` inside the prompt would close the literal early.
if '"""' in text:
    raise SystemExit("VERIFY_PROMPT.md contains a triple quote; cannot inline verbatim.")

source = TARGET.read_text(encoding="utf-8")

# The constant is a plain triple-quoted string with its first line on the
# assignment line, and may or may not carry an `f` prefix. Match either.
pattern = re.compile(r'_FALLBACK_VERIFY_PROMPT = (?:f)?""".*?"""', re.DOTALL)
match = pattern.search(source)
if not match:
    raise SystemExit("could not find the _FALLBACK_VERIFY_PROMPT assignment to replace")

# Keep whichever prefix the file already had, so this does not silently change
# the constant into an f-string.
prefix = "f" if match.group(0).startswith("_FALLBACK_VERIFY_PROMPT = f") else ""
new_literal = f'_FALLBACK_VERIFY_PROMPT = {prefix}"""{text}"""'

updated = pattern.sub(lambda _: new_literal, source, count=1)
if updated == source:
    raise SystemExit("no change made - the fallback already matched the file")

TARGET.write_text(updated, encoding="utf-8")
print(f"synced {len(text)} chars of VERIFY_PROMPT.md into _FALLBACK_VERIFY_PROMPT")
