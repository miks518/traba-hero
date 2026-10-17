# Decision record — the anomaly rename

**The scan's findings are `anomalies`, not `red flags`.** Renamed across the whole
stack on 2026-10-07.

Renamed artefacts: `Anomaly` (schema + TS type), `anomalies` (wire key), `ANOMALY:`
(prompt line prefix), `END ANOMALIES`, `_anomalies()` (backend factory),
`AnomaliesList` / `AnomalyCard` (components), `anomalyCount` (`riskDisplay`).

**Update 2026-10-18.** `AnomaliesList` no longer exists — the report panel replaced
it with `AnomalyCards`, which owns its own section heading and renders the rule
code and the posting's quoted span. `AnomalyCard` survives and is still used, by
the Match tab rather than the report. The legacy *wire* paths above are all
untouched and still deliberate; see the note further down this file.

**Why:** "red flag" is a *conclusion* delivered as a category label, before the reader
sees any evidence. A `low`-severity note about formatting was announced with the same
force as a request for an advance fee, which is what panelists reported. An anomaly
asserts only that the posting differs from the ordinary case; what that difference
*means* is the reader's to draw.

This is the burden-of-proof rule the rest of the system already follows in four places
— `SearchOutcome.ok`/`.results` independence, never-`red`, the `POSTING ANALYSIS` word
ban, and `CompanyNameNeeded`'s dashed border. **The label was the last surface
contradicting it.**

Reasoning: `docs/superpowers/specs/2026-10-07-framing-origin-false-positives-design.md`
§6.

## What did NOT change

The severity ladder, `POSTING_SEVERITY_WEIGHTS`, and any number the panel displays.
"Anomaly" is the category noun; `low`/`mid`/`high` is still what carries weight.

**The inner JSON key stays `flag`**
(`{"flag": "...", "reasoning": "...", "severity": "..."}`) — renaming it would touch
the wire format for no reader-visible gain.

## Three legacy paths are deliberate, not leftovers

**Do not "clean them up".**

- **`lm_client._SECTION_RE` accepts `RED FLAG` alongside `ANOMALY`/`ANOMALIES`**, the
  same way `EMPLOYER NAME` is accepted alongside `COMPANY NAME` — a scan recorded
  before the rename still parses.
- **`_parse_custom`'s placeholder filter lists both spellings** ("no anomalies", "no red
  flags"). A model asked for one may answer with either, and a surviving placeholder
  becomes a finding *with a severity*, so it adds to the score. The test asserts a real
  anomaly beginning "No visible evidence…" is **not** dropped, which is the
  overcorrection to guard.
- **`migrateScannedJobs` moves a stored `redFlags` array onto `anomalies`.** Without it
  every scan taken before the rename renders as a **clean posting** — the findings are
  in storage under the old key and nothing reads them. It destructures rather than
  spreading `undefined`, since a key set to `undefined` still exists. Measured scores
  are left alone; only the field is renamed.

---

## The 11 failing tests, and why the earlier note about them was wrong

`test_scan_prompt_file.py` had 11 failures. **They are fixed, and the note that called
them pre-existing was wrong.**

An earlier version of `UNFINISHED-WORK.md` described them as predating the anomaly
rename and not worth reading as rename damage. That was half right and dangerous in the
wrong direction: they *did* predate the rename, so they read as unrelated, but they
were not stale tests.

**Commit `a84da6f` (2026-09-30) rewrote `SYSTEM_PROMPT.md` and dropped the entire
guardrail block, while `prompts.py`'s fallback kept it.** The prompt the backend
actually loads is the file, so the deployed scan had been running without the absence
rule, the quotable-evidence rule, pattern-needs-its-element, never-invent,
`task-for-earning`, and work-then-payment-is-ordinary. Restored in `86cff03`; the
backend suite is green.

**A red test in this repo is a finding, not a condition.** The failure mode was not
that nothing caught it — the tests did — but that it sat red long enough to be written
down as "known", which is how a live safety regression becomes background.
