# Decision record — resume input paths

The Match tab takes a profile two ways: a resume file upload, and a manual form. This
record holds the why behind that split, the asymmetry a future reader will want to
"fix", and the consent gate. The mechanics — storage keys, caps, wire stripping — are in
`docs/architecture.md` under "Resume input paths" and are not repeated here.

---

## The manual path exists for a privacy reason, and the reason shapes everything else

A resume is the densest personal document a job seeker owns: name, address, phone,
email, every employer, dates, education. Sending it anywhere so a model can pull out ten
skill words is a bad trade, and the user said so.

**The manual form makes the model's input exactly what the user chose to type.** No
parsing, no extraction, no file. The privacy surface of the profile step is the four
fields the reader filled in, and traceability gets cheaper rather than more expensive:
a typed skill is traceable to the user by definition, where an extracted one needed the
evidence-snippet machinery the old plan built.

**It also deleted a plan rather than implementing it.** `jobposts/ResumeExtractionPLAN.md`
(untracked scratch) proposed deterministic extraction — skillNer, an ESCO PhraseMatcher
gazetteer, server-side caching, a structured job summary. A review found the plan was
written for a different codebase, carried a server-side cache that violated
`docs/decisions/security-boundaries.md`, and would take days. The manual path dissolves
the problem instead of solving it: there is nothing to extract. **Do not resurrect that
plan for this purpose.** If extraction ever returns, it is a new decision with a new
privacy analysis.

---

## The persistence asymmetry is deliberate — do not "fix" it

**A manual profile persists in `chrome.storage.local` under `manualProfile`; an uploaded
resume's profile never leaves panel state.** A reader who closed the panel and lost ten
typed answers would reasonably never type them again, so the manual profile comes back
with the panel. An uploaded resume produces a profile derived from a whole document —
the extracted fields can carry anything the file held. The conservative default is to
keep derived personal data out of storage, so the upload behaves as it always has:
session-only.

Both directions are load-bearing:

- persisting uploaded profiles is a policy change, not a cleanup;
- dropping manual persistence makes the manual path unusable in practice.

`App.tsx` owns the split (`handleResumeData`, `handleClearResume`). A saved manual
profile is replaced, not merged, when a resume is uploaded, and removed when the profile
is cleared.

---

## `source: 'manual'` is a frontend-only marker

It exists so the preview card can say "Manual Profile" instead of claiming a resume was
read that never was. `lib/api.ts` strips it in `toWireResume` before either match
request, because the backend schema has no such field. **Do not wire it through to the
backend** — the backend never asked where a profile came from, and nothing downstream
reads it. If a future feature needs provenance on the wire, that is a schema change with
its own record.

---

## The consent gate covers the upload and only the upload

`ConsentModal` opens before the first upload and before the network call; accepting
stores `hasConsentedPrivacy` (`lib/privacyConsent.ts`), and only a stored `true` counts —
a missing key, `false`, or unreadable storage all read as "ask again", because the safe
direction for a consent gate is one extra notice, never a skipped one.

**The manual path is not gated, on purpose.** It sends nothing when saved; the only
network call it ever reaches is the match request, which the reader fires themselves, on
data they just typed. Gating it would imply something happens at save time that does not.

The notice's retention sentence is enforced, not decorative: the backend holds nothing
(`docs/decisions/security-boundaries.md`), and
`backend/tests/test_resume_content_not_logged.py` keeps extracted content out of the
server logs. **If either changes, the modal text changes first** — the notice must not
outrun the code.

---

## The log trim covers the flows that carry personal data

`resume_flow.py` and `match_flow.py` log token and character counts, never content — the
model's answer is written out of the reader's resume, and a log line is a copy on disk.
This includes parse-failure paths: malformed output is still made of the reader's data.

**`scan_flow.py` and `offer_flow.py` still log raw output, deliberately.** Their content
is the posting under third-party assessment, not the user's resume, and their logs are
the main diagnostic for scan-drift. Stripping them belongs to the wider zero-retention
audit of CRITICAL.md Task 2.2, which stays open. Neither direction is a drive-by: do not
extend the trim to scan/offer as cleanup, and do not restore the resume dump for
debuggability — parse drift is diagnosed from the counts plus the parser fixtures.

---

## Where the pieces live

| Piece | File |
|---|---|
| Profile builder, caps, storage helpers | `entrypoints/sidepanel/lib/skillsProfile.ts` |
| The form | `entrypoints/sidepanel/components/match/SkillsProfileForm.tsx` |
| Consent storage | `entrypoints/sidepanel/lib/privacyConsent.ts` |
| The notice | `entrypoints/sidepanel/components/match/ConsentModal.tsx` |
| The asymmetry + gate wiring | `entrypoints/sidepanel/App.tsx`, `views/ResumeMatchView.tsx` |
| Content-free logging | `backend/app/services/scanner/resume_flow.py`, `match_flow.py` |
| The tests that hold it all | `skillsProfile.test.ts`, `ConsentModal.test.tsx`, `ResumeMatchView.consent.test.tsx`, `App.test.tsx`, `backend/tests/test_resume_content_not_logged.py` |
