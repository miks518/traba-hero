"""Live probe: does the scan read a chat header as an employer?

Run from `backend/`:

    python scripts/live_employer_probe.py jobposts/tasktoearn.jpg

**This calls the live AI provider.** It is not part of the offline suite and
must never be added to it. It is a manual instrument for one field question:
`EMPLOYER NAME` on a screenshot of a chat, where the top bar is the sender's
display name rather than a letterhead.

What to look for:

- `employer` is `None` (the wire value for `Not stated`), and
- the `ANOMALY` list still carries the finding, and
- the sender label lands in `CONTACT_METHOD` as a messaging channel, if anywhere.

A regression reads as `employer = "Megan May"`: a person's display name sent to
`/api/verify` as a company.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.rate_limit import limiter  # noqa: E402

MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def _result_frame(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        frame = json.loads(line[len("data:"):].strip())
        if frame.get("type") == "result":
            return frame.get("data") or {}
        if frame.get("type") == "error":
            raise RuntimeError(f"stream error: {frame.get('error')}")
    raise RuntimeError("no result event")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    image_path = Path(argv[1])
    if not image_path.exists():
        print(f"no such file: {image_path}")
        return 2

    suffix = image_path.suffix.lower()
    if suffix not in MIME:
        print(f"unsupported extension: {suffix}")
        return 2

    encoded = base64.b64encode(image_path.read_bytes()).decode()
    limiter.enabled = False
    with TestClient(app) as client:
        response = client.post(
            "/api/scan",
            json={"images_base64": [encoded]},
        )
    if response.status_code != 200:
        print(f"HTTP {response.status_code}: {response.text[:300]}")
        return 1

    data = _result_frame(response.text)
    anomalies = data.get("anomalies") or []
    attributes = data.get("attributes") or {}
    employer = data.get("company_name")

    print(json.dumps({
        "employer": employer,
        "request_class": data.get("request_class"),
        "verification_context_present": "verification_context" in data
        and data["verification_context"] is not None,
        "codes": [a.get("code") for a in anomalies],
        "labels": [a.get("flag") for a in anomalies],
        "quotes": [a.get("quote") for a in anomalies],
        "CONTACT_METHOD": attributes.get("CONTACT_METHOD"),
        "COMPANY": attributes.get("COMPANY"),
        "CLAIMED_TYPE": attributes.get("CLAIMED_TYPE"),
        "PAY": attributes.get("PAY"),
        "posting_analysis": (data.get("posting_analysis") or "")[:300],
    }, ensure_ascii=False, indent=2))

    ok = employer is None
    print()
    print("employer is Not stated:", ok)
    if not ok:
        print(f"  REGRESSION: the scan took {employer!r} as the employer and would "
              "search for it as a company")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
