# Decision record — verification design

Owner files: `backend/VERIFY_PROMPT.md`,
`backend/app/services/scanner/verification_prompt.py`,
`verification_parser.py`, `verification_flow.py`.

---

## The prompt file is the source of truth, and the module keeps a full fallback copy

`VERIFY_PROMPT.md` is what the backend loads; the in-module copy is a fallback.

The prose used to be a constant in `verification_prompt.py`, which meant editing a prompt
meant editing Python. It moved because this is the longest prompt and its rules are the
libel guardrail, so it needs to be readable and diffable in a text file.

`_FALLBACK_VERIFY_PROMPT` is kept **complete rather than reduced to a role line**: a
deployment shipping without the file must not verify against a stub.

**The two can drift** — that is the known risk. `test_verify_prompt_file.py` asserts they
currently agree, re-asserts the guardrails against the file the backend loads, and checks
the loader follows the file rather than the constant.

`VERIFY_SYSTEM_PROMPT = load_verify_prompt()` is evaluated at import, so **editing the
file needs a restart**, exactly as with the other three prompts.

---

## Exactly six claim categories

**Company Existence**, **Official Registration**, **Location / Branch**,
**Channel Match**, **Reputation**, **Similar Offers**.

- The first three were the old category list.
- `Location / Branch`, `Channel Match` and `Similar Offers` test *claims the posting made*
  rather than facts about a company name, **because a check that a real employer always
  passes cannot tell an impersonator from an employer.**
- "Company Name" and "Online Presence" were removed earlier as redundant — the scan
  already establishes whether a name was present, and the endpoint cannot run at all
  without one.
- "Scam Reports" + "Social Reputation" were merged into Reputation.

**Forbidding a seventh is load-bearing:** the score is a fixed weight table, so an
invented category has no weight and silently vanishes.

---

## Registration is not the same as the SEC

The category was `SEC Registration` until a test showed a company holding a DTI/PEZA/BOI/LGU
registration being reported as inconclusive.

It is now `Official Registration`, and the prompt names SEC, DTI, PEZA, BOI, a local
government unit business permit and government portal listings as equally valid.

**Scoring "no SEC number" against a company that has a DTI registration is a false
negative that made the card useless rather than merely cautious.**

`risk_calculator` maps the legacy `SEC Registration` label to the same weight, and
`verification_parser._LEGACY_LABELS` keeps stored results from logging a phantom missing
category.

---

## Each check returns the fact and its source, not a 20-word summary

The old `detail` cap discarded almost everything retrieval found: roughly 3,000
characters of results became three details of at most 20 words.

The schema now carries:

- `finding` — the one fact that decided the status, **uncapped**
- `source_title` and `source_url` — **copied exactly from the provided results, never
  constructed**
- a top-level `evidence` list the panel renders as clickable sources

**This is the only channel by which online evidence reaches the user, so a fabricated
URL here is a fabricated citation.** Binding it in code is recorded in
`docs/decisions/security-boundaries.md`.

---

## The text parser is the fallback, not the primary path

`verification_parser.py` splits the response into per-`VERIFY` blocks and extracts
`STATUS` and `DETAIL` from each independently, rather than matching the whole shape in
one regex — a single missing `END VERIFY` used to make one match span two blocks and
swallow a category.

It is now the **fallback** parser, used only when the provider does not honour structured
output.

---

## A partial parse is never silent

`verification_flow` logs
`[verify] Parsed N of 6 expected categories; missing: ...`.

`risk_calculator`'s weight table knows the six canonical labels plus the legacy
`SEC Registration`. **Any other legacy label such as "Scam Reports" parses and renders
but scores zero, because an unweighted label is silence rather than a default.**

---

## Status labels are named on the axis they are judged on

`green` / `yellow` / `red` render as **Supported** / **Not established** /
**Contradicted**.

`yellow` is amber in the card and that is deliberate — see
`docs/architecture.md` for the full rendering rule and its scope limit.
