"""Live probe: does the scan invent a fee on a posting whose number is a salary?

Run from `backend/` with the real provider configured:

    python scripts/live_money_probe.py

**This calls the live AI provider and spends tokens.** It is not part of the
offline suite and must never be added to it — `backend/tests/conftest.py` blocks
external network for exactly this reason. It is a manual instrument, run with
permission, for one field question: does the money rule hold on postings whose
only number is a salary?

The six postings are split so the result is falsifiable in both directions. Four
state a salary and no fee (the shape the 2026-11-03 field test reported twice);
two state a real fee, so the guard is proved to let one through rather than only
proved to drop a finding.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Run from `backend/` either as `python scripts/live_money_probe.py` (where
# `sys.path[0]` is `scripts/`) or as `python -m scripts.live_money_probe`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.rate_limit import limiter  # noqa: E402

CORPUS = [
    (
        "cashier-salary-only",
        False,
        "HIRING CASHIER - Makati City. Salary P18,000 to P22,000 per month plus "
        "P1,500 allowance. 13th month pay. Send your resume to hr@abccorp.ph",
    ),
    (
        "service-crew-range",
        False,
        "Now hiring service crew for our Quezon City branch. Pay range PHP "
        "16,500-19,000 per month depending on experience. Walk in with your resume.",
    ),
    (
        "warehouse-per-day",
        False,
        "Warehouse helper needed, Cavite. P610 per day plus overtime. AM shift. "
        "Message 0917 555 1234 for details.",
    ),
    (
        "driver-with-allowance",
        False,
        "Company driver, Ortigas. Monthly salary negotiable, fuel allowance "
        "provided, 13th month pay and SSS. Email cv to careers@logistics-ph.com",
    ),
    (
        "real-fee-gcash",
        True,
        "Hiring packers. Pay P350 processing fee via GCash to 0917 888 0000 "
        "before your interview. Start immediately after.",
    ),
    (
        "real-fee-uniform",
        True,
        "Machine operator, Laguna. Applicants must purchase their own safety "
        "uniform (P1,200) before the start date. Salary P15,000 per month.",
    ),
]

MONEY_CODES = {"FEE_MANDATORY", "FEE_CONDITIONAL", "PURCHASE_REQUIRED", "DEPOSIT_REQUIRED"}


def _scan(client: TestClient, text: str) -> dict:
    """POST /api/scan-text and return its final `result` event.

    The stream is `data:`-only JSON frames carrying a `type` key — there are no
    `event:` lines, which is why an `iter_lines` reader keyed on `event:` found
    nothing on a scan that had worked.
    """
    response = client.post("/api/scan-text", json={"text": text})
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")
    for line in response.text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        frame = json.loads(line[len("data:"):].strip())
        if frame.get("type") == "result":
            return frame.get("data") or {}
        if frame.get("type") == "error":
            raise RuntimeError(f"stream error frame: {frame.get('error')}")
    raise RuntimeError("stream ended with no result event")


def main() -> int:
    # The rate limit is per client address, and this probe is six scans from
    # one `testclient`. The limiter's 5/minute would make the sixth a 429 and
    # the run would report a pacing artefact as a result. Disabled for the
    # duration of the probe only; `test_rate_limit.py` owns the limiter's own
    # behaviour and none of this touches the suite.
    limiter.enabled = False
    rows = []
    with TestClient(app) as client:
        for name, expects_fee, posting in CORPUS:
            try:
                data = _scan(client, posting)
            except Exception as exc:  # noqa: BLE001
                rows.append({"case": name, "error": f"{type(exc).__name__}: {exc}"})
                print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
                # A 429 is a pacing problem, not a finding; say so rather than
                # letting the summary count it as one.
                continue

            anomalies = data.get("anomalies") or []
            codes = [a.get("code") or "" for a in anomalies]
            row = {
                "case": name,
                "expects_fee": expects_fee,
                "wire_money_codes": [c for c in codes if c in MONEY_CODES],
                "all_codes": codes,
                "finding_count": len(anomalies),
                "request_class": data.get("request_class"),
                "pay": (data.get("attributes") or {}).get("PAY", ""),
                "labels": [a.get("flag") for a in anomalies],
            }
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)

    leaked = [r for r in rows if not r.get("expects_fee", True) and r.get("wire_money_codes")]
    missed = [r for r in rows if r.get("expects_fee") and not r.get("wire_money_codes")]
    errored = [r for r in rows if "error" in r]

    print("\n=== summary ===")
    print(f"postings scanned:                        {len(rows)}")
    print(f"errors:                                  {len(errored)}")
    print(f"invented fees that reached the wire:     {len(leaked)}")
    print(f"real fees the guard dropped:             {len(missed)}")
    for r in leaked:
        print(f"  INVENTED FEE: {r['case']} {r['wire_money_codes']} {r['labels']}")
    for r in missed:
        print(f"  DROPPED A REAL FEE: {r['case']} {r['labels']}")
    return 0 if not leaked and not missed and not errored else 1


if __name__ == "__main__":
    sys.exit(main())
