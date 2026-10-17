# Decision record — parser and provider resilience

---

## `_SECTION_RE` alternation order is not cosmetic

`lm_client._SECTION_RE` also matches `ATTRIBUTES`, `COMPANY`, `LOCATION`,
`CONTACT_METHOD`, `MEETING_SPOT`, `PAY`, `QUERY_REF`.

Two details are load-bearing:

- It spells the two-word attributes `CONTACT[_\s]*METHOD` and `MEETING[_\s]*SPOT`, not
  `\s*`, because the **underscore form is what the prompt and the tests emit**.
- **`COMPANY NAME` must precede `COMPANY`**, or the shorter alternative matches first
  and the legacy employer path is destroyed.

---

## The five attribute keys are gated on `in_attributes`

The section is opened by the `ATTRIBUTES` line and closed by `END ATTRIBUTES` **and by
any other keyword**.

They are ordinary English words — `Company states applicants should bring their own
laptop.` matches `COMPANY` — and the colon is optional for every key, so a section body
is full of lines that match them.

Reading one as a key did two things at once:

1. it stored the sentence in `attributes`, which `build_scheme_queries` then turned into
   a credit spent on a query nothing can satisfy, and
2. because a matched keyword closes the section first, it truncated `POSTING ANALYSIS`
   at that line.

**The verdict was gone with no error anywhere**, and `JOB SUMMARY` could vanish
**entirely**, since `close_section` writes no key at all for an empty buffer.

**A rejected line is appended back to the section buffer, not dropped** — dropping it
truncates the same way with the same silence.

The gate is the *block*, not the colon, so `QUERY_REF` is not gated either (it is not an
attribute) and `COMPANY NAME` still parses anywhere.

---

## `SEARCH QUERIES` / `QUERY` are gone, not dormant

They were parsed, capped at three, shipped on `ScanResponse.search_queries`, and
governed by two prompt rules, and **nothing read them**.

They were **deleted rather than left matching, because a section a parser still
recognises is a trap for the next reader.**

`test_a_query_line_is_no_longer_a_section` is the tombstone, and it asserts the employer
path still parses beside them so it cannot be satisfied by a parser that stopped reading
everything.

---

## `END ATTRIBUTES` is a bare terminator and is deliberately not in `_SECTION_END_KW`

Treating a terminator as a section end would reset `matched_any` and make a valid scan
parse as nothing.

---

## A parameter rejection arrives as a 404, not only a 400

`_rejected_param` recognises two shapes:

- A **provider-issued** rejection is a 400 naming the parameter.
- An **unroutable** one is a 404 — `'No endpoints found that can handle the requested
  parameters'`, `failed_routing_step: Filter by Parameters` — which is what a model with
  no schema-capable endpoint produces, and the more common of the two.

The 404 branch was missing entirely, so a scan that succeeded on a new model took
`/api/verify` down with it, since only verify sends `response_format`.

**The status alone is not enough to match on:** a 404 is also what a mistyped
`MODEL_NAME` returns, and treating that as a capability gap would report the wrong
problem. The message markers are required and a genuine 404 still propagates.

When the message does not name the parameter, the culprit is worked out from what has
already been dropped, `_ROUTING_FALLBACK_ORDER` trying `structured` first (it travels
with `provider.require_parameters`, the flag that makes routing strict) and `reasoning`
last.

`verification_parser` then reads the plain-text response, so a model without structured
output degrades rather than fails.

`test_lm_param_fallback.py` uses the real error body from a failing deployment, and covers
the 404, the genuine-404, the 429, and the give-up path.

---

## `verification_parser` raises on an unparseable response

`VerificationParseError` is raised when the response contains no VERIFY block.

Returning `[]` for unparseable text let a failed verification render as a panel with
nothing on it and no error anywhere, because the request itself had succeeded. **"Parsed
and reported nothing" is a different claim and still returns `[]`**; the flow renders
that with its own notice.

`EXPECTED_CATEGORIES` is **derived from** `verification_prompt.VERIFY_CLAIM_CATEGORIES`
rather than restated, because three places naming the categories is how they drifted apart
once already.

It is a *diagnostic* list and nothing more — parsing accepts whatever label it is given,
since a result recorded before a rename carries a label this tuple no longer names.
