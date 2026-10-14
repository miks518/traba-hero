# Deployment fences: CORS pinning and a path token

**Date:** 2026-10-14
**Status:** awaiting approval

## What this is

Two cheap fences in front of an API that, after removing the client key, is
reachable by anyone who can reach the URL.

Neither stops a determined attacker. Both stop the large population that is not
one, at no ongoing cost and with nothing for the user to configure. A third fence
— a spending ceiling at OpenRouter — is left to the operator, because it is
configuration rather than code and it is the one that holds against patience.

## What it is not

Not authentication. A browser will generate credentials for an attacker as
readily as for a user, and Chrome removed Token Binding in 2024 for exactly that
reason. Anything claiming to solve caller identity for a browser extension on
desktop Chrome is either solving a different problem (token *replay*) or does not
exist. `documentation/` and `AGENTS.md` already record this; this document
extends it with what is actually being done instead.

## Fence 1 — the path token

A random segment in the route: `/api/<32-hex>/scan` instead of `/api/scan`.

**Stops:** un-targeted scanning, and drive-by from a website that guesses common
API paths. **Does not stop:** anyone who opens the extension bundle, where the
token is plainly visible.

It is labelled security-through-obscurity wherever it is described, because that
is what it is, and because a reader who believes it is authentication will make
decisions on the strength of a belief that does not hold.

### Implementation

A new `API_PATH_TOKEN` setting on the backend.

- **Unset** → routes mount at `/api/scan`, exactly as today. Local development
  is unchanged and needs no configuration.
- **Set** → routes mount at `/api/<token>/scan`.

Mounted as a router prefix rather than a path parameter, so there is no
comparison to make: an unknown path is simply not routed, and FastAPI answers
`404`. That is better than a header check — a wrong token gets no confirmation
that anything exists there, rather than a `401` that confirms the endpoint is
real.

The frontend gains `WXT_API_PATH_TOKEN` (WXT exposes any `WXT_`-prefixed
variable to the client, same as the existing `WXT_API_BASE`). One line in
`api.ts` decides the prefix:

```ts
const API_PREFIX = API_PATH_TOKEN ? `${API_BASE}/api/${API_PATH_TOKEN}` : `${API_BASE}/api`;
```

`WXT_API_BASE` stays a bare origin. It was already effectively that — it carried
`/api` only because the token was not yet in the path.

### `/health` stays at the top level

Deliberately **not** moved behind the token. It costs no provider credits,
reveals nothing about the service, and leaving it in its conventional place
means a deployment health check or uptime monitor needs no token. Uniformity
would be tidier; a deploy that fails confusingly is worse. Recorded here so the
inconsistency reads as a decision rather than an oversight.

## Fence 2 — CORS pinned to the extension origin

`allow_origins=["*"]` with `allow_credentials=True` currently lets **any website
a user visits** call the backend through their browser. The shared key used to
block that by accident; with it gone, there is nothing behind it.

New `CORS_ALLOWED_ORIGINS` setting, comma-separated.

- **Unset** → the CORS middleware is not installed at all, and a startup log
  says so. Browsers then block cross-origin calls, which is safe by default.
  This is the opposite failure to `CLIENT_SECRET_KEY` being unset, which meant
  "disabled and silent" — a removed scheme should not leave its shape behind.
- **Set** → only those origins are allowed.

This stops the entire web. It does not stop `curl`, which never sees CORS.

### The extension ID has to be pinned, and this needs a key

An unpacked extension gets a **different ID every time it is reloaded from
disk**, so the server cannot know it in development. Pinning it requires a
`key` field in the manifest: the DER-encoded public key, base64-encoded, in the
manifest. The extension ID is derived from it, so the ID stays the same in
development, in the Web Store, and across every future republish.

This is a **public** key — it is present in every published manifest, so nothing
secret is committed. **My call, flagging it because it is permanent:** once the
Web Store sees this key, the extension ID is fixed for the life of the listing.
That is the intent, but it is the kind of decision that should be made
deliberately.

## Tests

Written first, in the shape this project uses — a hostile-input suite is
useless if it only tests the happy path.

| Test | Asserts |
|---|---|
| Token set: correct path works | `/api/<token>/verify` returns 200 |
| Token set: bare path is gone | `/api/verify` returns **404**, not 401 |
| Token unset: bare path still works | local development unchanged |
| Token unset: no token path | `/api/<anything>/verify` 404s |
| `/health` unaffected by the token | reachable at the top level either way |
| CORS unset: middleware absent | no `Access-Control-Allow-Origin` on any response |
| CORS set: extension origin allowed | correct `Access-Control-Allow-Origin` |
| CORS set: another origin refused | no allow-origin header for `https://evil.example` |
| **CORS is never `*` in shipped config** | reads `backend/.env.example` and asserts |

That last one is the regression guard for the thing that actually bit us.

Each fence is mutation-checked in both directions: restoring `*` fails the
CORS guard, and dropping the token from the prefix fails the path tests.

## Global constraints

- The suite stays **fully offline**. Nothing here may reach a provider.
- `happy-dom` performs no layout; these are server-side tests, so that is moot.
- CORS is read from settings, never hardcoded — the extension ID is a
  deployment fact, not a source constant.

## Accepted losses

- The token is visible in the bundle. Documented, not defended.
- CORS does not stop non-browser clients. Nothing on this platform does.
- Neither fence survives someone who reads the extension's source.

## Still not done

The spending ceiling. That is the fence that holds against all of the above,
and it is the operator's to set.