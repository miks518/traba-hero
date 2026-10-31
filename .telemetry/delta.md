# Delta: Current → Target

Scanned 2026-10-31. Current state is greenfield (`current-state.yaml`): zero
tracking exists in either the extension or the backend, so the delta has a
single non-empty section.

**ADD + RENAME + KEEP = 8 + 0 + 0 = 8 = total target events. ✔**

## Add (not tracked today)

Priority order marks what ships first. Backend-derived events are cheapest —
they need no client change and no consent-notice change; the backend is already
the observer of those moments. Client events touch the consent surface second.

| Event | Category | Emitted by | Why | Priority |
|---|---|---|---|---|
| `scan.started` | core_value | backend | The primary value action begins; input_type makes scan-text's zero-usage state countable | 1 |
| `scan.completed` | core_value | backend | The value action's main outcome; `anomaly_codes` bag carries the taxonomy-drift signal (`OTHER` rate) at zero new vocabulary | 1 |
| `scan.failed` | core_value | backend (+client for offline shapes) | Failure *shapes*, distinct: limiter refusals vs empty responses vs provider errors | 1 |
| `assessment.completed` | core_value | backend | The verdict the product exists to produce: grid-word distribution, parse degradation, the letting-down-rates of each finding status, and the code-owned channel rule — all from fields already on the backend's own objects | 1 |
| `offer.completed` | core_value | backend | The model-owned-level path stays observable; if its reliability ever gets revisited (AGENTS.md decision 5), this is the record of how often it runs | 2 |
| `match.completed` | supporting / core_value | client | Resume-match usage, profile path split. Client-emitted because `profile_source` must never enter the backend schema | 3 |
| `upload.consent_granted` | configuration | client | The RA 10173 gate's accept/decline-retry rates — the privacy-criticial path's adoption signal, without recording who or when | 3 |
| `connectivity.changed` | lifecycle | client | Offline-banner quality: flaps vs genuine outages | 4 |

## Remove (tracked today, shouldn't be)

Nothing — nothing is tracked today. The *diagnostic logs* the audit recorded are
not removed by this plan either: content-free counters stay where they are
(`resume_flow.py`, `match_flow.py`, `search.py` timings), because they back the
existing zero-retention tests and serve debugging, not analytics.

## Rename

Nothing exists to rename. Naming convention decision: `object.action` snake_case
throughout — the greenfield default; nothing had to be preserved.

## Change (wrong shape)

Nothing exists to reshape.

## Snapshot metrics to start materialising (all operator-side aggregates)

The count-key decision of 2026-10-31 (daily-salted hash + per-day
HyperLogLog sketches) adds the user-count family the product otherwise cannot
answer — with no per-key record ever existing and no event growing an ID.

| Metric | Source | Why first |
|---|---|---|
| `daily_active_users` / `weekly_active_users` / `monthly_active_users` | count-key sketch unions | The request that triggered the decision: real user counts, identity-free |
| `returning_ratio` | sketch intersection, window-bounded | The only "how many came back" the unlinkability design permits |
| `assessment_distribution` | assessment.completed | The product's core outcome over time |
| `anomaly_code_distribution` + `other_code_rate` | scan.completed | Taxonomy drift — the `OTHER` spike is the documented early-warning signal |
| `parse_fallback_rate` | assessment.completed | Structured-output degradation visibility |
| `missing_employer_rate` | scan.completed | The "missing input not a finding" reality, quantified |
| `scans_started_total` / `scans_failed_by_class_total` | scan.* | Volume and reliability |
| `consent_retry_rate` | upload.consent_granted | Whether the consent gate is doing its job or punishing the reader |

## The two decisions this delta does not make

1. **"Was this accurate?" verdict feedback** — the panel's most valuable absent
   slot. Its event would be trivial to add; its *destination* is the problem:
   a reader comparing a verdict to reality is a store of employer-attached
   opinions, the exact shape the libel guardrail exists against. Deferred with
   a name (`verdict_feedback.*`), a preconditions list (decision record →
   consent text → event), and no marker in the plan above deciding it.

And the two it has made since:

1. **User counting** (decision 2026-10-31): daily-salted server-side hash at
   ingest, distinct-counted through per-day HyperLogLog sketches only. Adds no
   event, no client change, no wire field — see `count_key:` in
   `tracking-plan.yaml`. Committing the ingest endpoint writes its decision
   record and RA 10173 notice sentence first.
2. **Any identity** — remains excluded even with the count key: the hash is
   unlinkable by construction and never retains a per-key record, so it buys
   DAU counts without ever becoming a pseudonymous ID to track. The earlier
   strictly-anonymous decision stands; the count key lives outside events,
   not inside them.
3. **Storage** (decision 2026-11-01): SQLite on a Railway volume
   (`TELEM_DB_PATH`), one writer, no application reads. Two tables —
   `daily_metrics` and `daily_sketch` — with the sketch table pruned to a
   30-day rolling window. The backend's "holds nothing" boundary is restated,
   not removed: **counts survive; keys and event bodies don't.** A missing
   volume degrades to in-process counters at startup with one log line, so an
   analytics outage can never ride the scan path. Postgres was rejected as a
   whole server for a one-file job.

## Cost note

Eight events, all low-to-medium frequency, none user-triggered high-frequency,
no per-event cost since the destination is first-party. The only ongoing cost is
the ingest endpoint's own rate-limit budget and body cap, both specified in
`implementation_notes`.
