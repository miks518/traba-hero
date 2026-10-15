"""Derive the extension ID from the COMPILED manifest, not from my own generator.

Generating the key and reading the ID back out of the same in-memory object would
prove nothing. This reads the string WXT actually wrote to
.output/chrome-mv3/manifest.json, base64-decodes it, and runs Chromium's
algorithm on those bytes. If the value survives the round trip, the ID is real.

The path is not a script to run repeatedly; it is the evidence for the value that
goes into backend/.env and Railway. Chrome remains the authority - the definitive
check is loading the extension and reading chrome://extensions.
"""
import base64
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COMPILED = REPO / ".output" / "chrome-mv3" / "manifest.json"
SOURCE = REPO / "wxt.config.ts"

EXPECTED = "hdmdhiojgdoomcjfhbkidbhkifmokkop"


def id_for_key(manifest_key: str) -> str:
    der = base64.b64decode(manifest_key)
    digest = hashlib.sha256(der).digest()
    return "".join(
        chr(ord("a") + (b >> 4)) + chr(ord("a") + (b & 0xF)) for b in digest[:16]
    )


compiled = json.loads(COMPILED.read_text(encoding="utf-8"))
key = compiled["key"]
derived = id_for_key(key)

print("compiled manifest key :", len(key), "chars")
print("decoded DER           :", len(base64.b64decode(key)), "bytes")
print()
print("ID derived from the compiled manifest :", derived)
print("ID written into wxt.config.ts comment :", EXPECTED)
print()
print("MATCH" if derived == EXPECTED else "MISMATCH - do not use either value yet")
print()
print("The real proof is still Chrome: load the extension and read the ID on")
print("chrome://extensions. If it differs from the value above, Chrome's is")
print("right and the manifest key is still valid - only the comment is wrong.")
