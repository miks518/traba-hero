# Decision record — reasoning models

`MODEL_NAME` may point at a reasoning model, which changes how a request fails.

**Deliberation is drawn from the same `max_tokens` budget that has to hold the answer**,
so a long think can consume the whole budget and return **nothing**.

`chat_stream_pieces` and `chat` both detect this and raise `EmptyModelResponse` naming
the model, `finish_reason`, and the reasoning character count, instead of handing an empty
string to a parser.

## An empty response has three causes, all previously indistinguishable

1. a mid-stream provider error frame — OpenRouter reports upstream failures, including
   rate limits on the routed provider, as a data frame inside an otherwise successful 200
   stream, so no HTTP error is ever raised
2. a model refusal, which arrives in `delta.refusal` and was never read
3. reasoning-only output, which goes to a provider-specific `reasoning` field the SDK does
   not declare

**The log now names which one.**

---

## Three ways to stop the budget being eaten, best first

All map to OpenRouter's normalized `reasoning` parameter and are off unless set.

1. **`AI_REASONING_ENABLED=false` turns reasoning off entirely.** The cleanest option and
   the one to try first. **It overrides the other two**, because a provider rejects a
   disabled reasoning combined with a high effort level, so sending them together would
   risk a 400 for no benefit.
2. **`AI_REASONING_EFFORT=low` reduces the thinking at the source.** The scan completes at
   `AI_MAX_TOKENS=2048` with this.
3. **`AI_REASONING_MAX_TOKENS=N` only truncates it**, and a truncated reasoning phase can
   make a provider re-attempt, so it is the weakest of the three.

**`exclude: true` is not a way to save tokens** — it only hides the reasoning from the
response while still paying for it.

---

## A model that cannot run with thinking off is retried with thinking on

A provider can accept `enabled: false` and still fail the request: some reasoning models
deliberate and answer with nothing, which surfaces as `EmptyModelResponse` — the user
sees "The AI service returned no content" for every scan with such a model.

When a request that went out with thinking disabled comes back empty, `chat` and
`chat_stream_pieces` retry it **once** with `enabled: true`. The retry is invisible on
the streaming path because `EmptyModelResponse` only ever fires before a content delta
was yielded, so the caller sees a longer wait, never duplicated output.

**A retry that produces content memorizes the model** in `_thinking_required_models`
(keyed by model id, process lifetime): later requests skip the doomed attempt and send
thinking enabled directly. This overrides a deployment's `AI_REASONING_ENABLED=false`
for that model — logged at info, never silent. A model that fails both ways is **not**
memorized: the memory records evidence that thinking-on works, nothing more.

The retry never fires when thinking was not disabled — an Advanced-scan request
(`thinking=true`) is reported, not redone — or when `reasoning` is already in
`_unsupported_params`, because then no reasoning body can be sent at all and the retry
would be the identical request twice.

---

## Rules

- **Keep `AI_MAX_TOKENS` above the reasoning budget.** Lowering it guarantees the failure
  it is meant to prevent.
- **Not every model supports disabling reasoning.** If the provider rejects the parameter,
  `_create_completion` retries once without it, logs
  `[lm] Provider rejected the reasoning parameter`, and stops sending it for the rest of
  the process.
- **A thinking-off request that answers with nothing is retried once with thinking on.**
  A success memorizes the model for the process; grep
  `[lm] thinking-on retry produced content` and
  `[lm] previously failed a thinking-off request` to see the fallback working.
- **The one-time `[lm] Generation config in use:` line records the config actually in
  force** — grep for it when a failure happens.
- **Some providers mirror the same text into both `reasoning` and `reasoning_content`.**
  The counter counts an identical pair once, so a failure reporting exactly double the
  previous figure is the instrumentation, not the model.
