# Chrome Web Store — Privacy Practices answers

Paste these into the Developer Dashboard → **Privacy practices** tab, then
**Settings** for the contact email. This is the standard pre-publish checklist;
it is not a problem with the package.

---

## Single purpose description
> Traba-Hero scans a job posting the user selects and assesses it for job-scam
> signals, verifies the named employer, and matches the user's resume against
> scanned postings.

(One sentence. Chrome rejects multi-purpose descriptions.)

---

## Permission justifications

### activeTab
> Grants temporary access to the current tab only when the user actively starts
> a scan (toolbar click or the floating button). Used to capture the job posting
> the user selects. No access is retained outside that user action.

### host permission use (`<all_urls>`)
> Job postings appear on arbitrary third-party sites (Facebook, LinkedIn,
> JobStreet, Indeed, OLX, messaging web apps). The user explicitly picks the
> element to scan, and the content script must be able to read and screenshot
> that region on whatever page it is on. The extension never reads pages the
> user has not selected.

### host permission use (`https://traba-hero-production-b6b9.up.railway.app/*`)
> The extension's own analysis backend. The selected job posting image or text is
> sent here to be assessed, and the result is streamed back. This is not a
> third-party site; it is the service the extension exists to call.

(The development manifest uses `http://localhost:8010/*` in this slot;
`store_prep.py` swaps it for the production origin in the uploaded package.)

### remote code use
> No, I am not using remote code.
> All JavaScript is bundled at build time and shipped inside the extension
> package. The extension loads no scripts, modules, or eval'd strings from any
> remote source. It sends a captured image or text to a backend API and receives
> only data back.

### sidePanel
> Opens the extension's side panel so scan results appear alongside the job
> posting without navigating away. Opened only in response to the user clicking
> the toolbar icon or the in-page button.

### storage
> Saves small pieces of user-local state in `chrome.storage.local`: the chosen
> theme, text size, the FAB toggle, and the user's scan history. Nothing is
> synced or sent anywhere; it stays on the device.

**`tabs` is not requested.** Version 0.5.0 was rejected for "requesting but not
using" it, and the rejection was correct: the active tab is located with
`tabs.query`, screenshotted with `tabs.captureVisibleTab`, and messaged with
`tabs.sendMessage`, none of which need that permission — the `<all_urls>` host
permission above already allows all three.

---

## Data usage / Data collection disclosures

**Does your extension collect or use user data?** Yes — declare the following:

| Data type | Collected? | Notes |
|-----------|-----------|-------|
| Website content | **Yes** | The job posting image/text the user chooses to scan, sent to the analysis backend |
| User-provided content | **Yes** | Resume file the user uploads for matching (in-memory only, not stored server-side) |
| Personally identifiable information | **Yes (limited)** | A resume may contain a name/contact details; processed in-memory only |
| Authentication info | No | — |
| Financial info | No | — |
| Health info | No | — |
| Location | No | — |
| Web history | No | — |
| Personal communications | No | — |
| User activity | No | — |

**Data usage certify (check all three):**
- ☑ Data is **not** sold to third parties
- ☑ Data is **not** used for purposes unrelated to the item's single purpose
- ☑ Data is **not** used to determine creditworthiness or for lending

**Data retention / justification text (if asked):**
> Screenshots and resume text are processed in memory to perform the analysis
> the user requested and are not persisted by the backend. Scan history is
> stored locally in the browser only.

---

## Settings / Account page (manual steps)

- **Contact email** — enter a support email and **verify it**. Chrome sends a
  confirmation link; you must click it before publishing. This is one of the
  checklist items ("You must verify the publisher's contact email").
- **Privacy policy URL** — a hosted URL is required because the extension
  transmits user data. Host one (GitHub Pages is fine) and paste the link.

---

## Note on `localhost` host permission

The development manifest ships:

```json
"host_permissions": ["<all_urls>", "http://localhost:8010/*"]
```

`http://localhost:8010/*` is a development endpoint. For the published build
`store_prep.py` removes it and requests the production origin instead:

```json
"host_permissions": ["<all_urls>", "https://traba-hero-production-b6b9.up.railway.app/*"]
```

The published manifest should request the origin the published extension really
talks to, not localhost.
