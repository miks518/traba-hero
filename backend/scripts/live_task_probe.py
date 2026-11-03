"""Live end-to-end: scan the screenshot, then assess the offer.

Mirrors the extension: `/api/scan` returns no employer, so the panel calls
`/api/analyze-offer` with the scan's findings. That is the path that decides the
colour for a task-to-earn DM.

    python scripts/live_task_probe.py ../jobposts/tasktoearn.jpg
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


def _result(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            frame = json.loads(line[5:].strip())
            if frame.get("type") == "result":
                return frame.get("data") or {}
    raise RuntimeError("no result frame")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    encoded = base64.b64encode(Path(argv[1]).read_bytes()).decode()
    limiter.enabled = False
    with TestClient(app) as client:
        scan = _result(client.post("/api/scan", json={"images_base64": [encoded]}).text)
        print(json.dumps({
            "stage": "scan",
            "company_name": scan.get("company_name"),
            "request_class": scan.get("request_class"),
            "codes": [a.get("code") for a in scan.get("anomalies") or []],
            "verification_context": scan.get("verification_context"),
        }, ensure_ascii=False, indent=2))

        if scan.get("company_name"):
            print("\ncompany_name present -> the panel would call /api/verify, not the offer path")
            return 0

        offer = _result(client.post("/api/analyze-offer", json={
            "text": scan.get("job_summary") or "",
            "company_name": "",
            "anomalies": [
                {"flag": a.get("flag"), "reasoning": a.get("reasoning"),
                 "code": a.get("code"), "quote": a.get("quote")}
                for a in scan.get("anomalies") or []
            ],
        }).text)

    breakdown = offer.get("assessmentBreakdown") or {}
    print(json.dumps({
        "stage": "analyze-offer",
        "assessment": breakdown.get("assessment"),
        "rule": breakdown.get("rule"),
        "exposure": breakdown.get("exposure"),
        "establishment": (breakdown.get("establishment") or {}).get("state"),
        "codes": breakdown.get("codes"),
        "what_to_check": offer.get("what_to_check"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
