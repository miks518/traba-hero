# Trusted-proxy rate limiting — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the rate-limit identity come from the socket peer unless the request actually arrived from a proxy the operator has named, so a caller cannot rotate `X-Forwarded-For` to escape its budget.

**Architecture:** A new `trusted_proxies` setting holds a comma- or whitespace-separated list of IPs and CIDR blocks. `_parse_trusted_proxies()` turns it into `ipaddress` networks. `_get_client_ip()` consults `request.client.host` first and reads `X-Forwarded-For` / `X-Real-IP` **only** when that peer is inside one of those networks. An empty list trusts nothing, which is the fail-closed default.

**Tech Stack:** Python 3.12, FastAPI, Starlette requests, slowapi, pydantic-settings, stdlib `ipaddress`, pytest.

**Spec:** `docs/security-audit-2026-10-14.md`, finding 1 (`rate-limit-key-trusts-client-x-forwarded-for`). The plan argues from that document; executors read both.

## Global Constraints

- **The test suite must stay fully offline.** Never make a live OpenRouter or Tavily call. Mock at the module boundary, exactly as `backend/tests/conftest.py` already does.
- **Never construct `Settings()` directly in a test that asserts a shipped default.** Use `class_settings(monkeypatch, **overrides)` from `backend/tests/conftest.py`. `_env_file=None` alone is not sufficient — it skips `backend/.env` but a real OS environment variable still overrides the class default.
- **`backend/tests/test_env_example.py` asserts every `Settings` field appears in `backend/.env.example`.** Adding the field in Task 1 without adding the key to `.env.example` fails that test.
- **Mutation-check every test in both directions.** Confirm it fails when the production code is reverted, *and* confirm the overcorrection fails too. A test that passes after you break the fix was testing nothing.
- **PowerShell traps in this repo:** `git commit -m` with quotes, multi-line text or em dashes breaks argument parsing — write the message to a file in the scratch directory and use `git commit -F <file>`. Inline `python -c` with quotes fails; write a `.py` file instead.
- **Do not weaken an existing test to make it pass.** `backend/tests/test_rate_limit.py` currently *asserts the vulnerable behaviour as intended*; Task 2 rewrites it deliberately.

## Review Focus

Five conditions this spec implies that a naive implementation gets wrong. Each gets its test in the task that owns the code.

1. **IPv4-mapped IPv6 peer.** uvicorn commonly reports the peer as `::ffff:127.0.0.1`. A naive string comparison against a trusted list containing `127.0.0.1` will not match, so localhost is treated as untrusted and the header is ignored — the limit silently over-counts in development.
2. **Empty list in a proxied deployment.** With `TRUSTED_PROXIES` unset behind Railway, every request shares one bucket. That is the fail-closed direction and is correct, but it is also the failure most likely to surprise the operator, so it must log loudly at startup and say what to set.
3. **A malformed entry.** A stray word, a trailing comma, or an empty element in `TRUSTED_PROXIES` must be dropped, not raise — a typo in a cost/security setting must never become an outage or, worse, silently widen trust.
4. **Which hop is chosen when the peer *is* trusted.** The leftmost element of `X-Forwarded-For` is caller-supplied; the rightmost is the address the trusted proxy observed. Taking the leftmost re-introduces the original bug for every deployment that appends rather than overwrites.
5. **A present-but-empty header.** `X-Forwarded-For: ` is falsy in Python and falls through to the socket peer. A naive `if "x-forwarded-for" in request.headers` would split an empty string and index into nothing.

---

### Task 1: The `trusted_proxies` setting and its parser

**Files:**
- Modify: `backend/app/config.py` (add one field to `Settings`)
- Modify: `backend/.env.example` (add the key — `test_env_example.py` requires it)
- Create: `backend/tests/test_trusted_proxies.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `Settings.trusted_proxies: str = ""` — comma- or whitespace-separated IPs and CIDR blocks.
  - `app.rate_limit._parse_trusted_proxies(value: str) -> list[IPv4Network | IPv6Network]` — normalised networks, silently dropping unusable entries. Imported by Task 2.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_trusted_proxies.py`:

```python
"""Parsing of the TRUSTED_PROXIES operator setting."""
import pytest
from ipaddress import IPv4Address, IPv6Address

from app.rate_limit import _parse_trusted_proxies


def test_empty_yields_no_networks():
    assert _parse_trusted_proxies("") == []
    assert _parse_trusted_proxies("   ") == []
    assert _parse_trusted_proxies(None) == []


def test_bare_ip_becomes_a_single_host_network():
    (network,) = _parse_trusted_proxies("203.0.113.7")
    assert network.prefixlen == 32
    assert network.network_address == IPv4Address("203.0.113.7")


def test_cidr_is_preserved():
    (network,) = _parse_trusted_proxies("10.0.0.0/8")
    assert network.prefixlen == 8


def test_comma_and_whitespace_separated_entries_all_parse():
    networks = _parse_trusted_proxies("203.0.113.7, 10.0.0.0/8\t192.0.2.0/24")
    assert [n.prefixlen for n in networks] == [32, 8, 24]


def test_ipv6_is_accepted():
    networks = _parse_trusted_proxies("::1, 2001:db8::/32")
    assert len(networks) == 2
    assert networks[0].version == 6


@pytest.mark.parametrize("bad", ["", " ", "not-an-ip", "999.1.1.1", "10.0.0.0/33", ",,"])
def test_unusable_entries_are_dropped_not_raised(bad):
    # A typo must not raise; the operator's other entries must still load.
    assert _parse_trusted_proxies(bad) == []


def test_one_bad_entry_does_not_discard_the_good_ones():
    networks = _parse_trusted_proxies("203.0.113.7, oops, 10.0.0.0/8")
    assert len(networks) == 2


def test_ipv4_mapped_ipv6_matches_its_ipv4_form():
    """uvicorn reports the peer as ::ffff:127.0.0.1; a trusted 127.0.0.1 must match."""
    networks = _parse_trusted_proxies("127.0.0.1")
    assert IPv6Address("::ffff:127.0.0.1") in networks[0]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && python -m pytest tests/test_trusted_proxies.py -v`
Expected: collection error — `ImportError: cannot import name '_parse_trusted_proxies' from 'app.rate_limit'`

- [ ] **Step 3: Add the setting to `backend/app/config.py`**

Add one field to `Settings`, placed immediately after `tavily_exclude_domains`, carrying this comment verbatim:

```python
    # Networks whose forwarded headers we are willing to believe. Empty means we
    # believe none, so the rate-limit identity is always the socket peer — the
    # fail-closed direction. Behind a proxy this collapses every caller into one
    # shared bucket until the operator lists the proxy's ranges here, which is
    # why `rate_limit.py` logs a warning at startup while this is blank.
    trusted_proxies: str = ""
```

- [ ] **Step 4: Add the key to `backend/.env.example`**

Append a blank-valued `TRUSTED_PROXIES=` entry with a short comment above it. `test_env_example.py` parses this file and asserts every `Settings` field appears in it, so omitting this fails an existing test.

- [ ] **Step 5: Implement `_parse_trusted_proxies` in `backend/app/rate_limit.py`**

```python
def _parse_trusted_proxies(value: str | None) -> list:
    """Turn the TRUSTED_PROXIES setting into ipaddress networks.

    Entries are separated by commas or whitespace and may be bare IPs or CIDR
    blocks. Anything unparseable is dropped rather than raised: a typo in a
    security setting must not become an outage.
    """
```

Body: split on `re.split(r"[,\s]+", value or "")`, skip empties, wrap each
`ipaddress.ip_network(entry, strict=False)` in `try/except ValueError` and skip
on failure. Return the list. Annotate the return type as
`list[IPv4Network | IPv6Network]` using imports from `ipaddress`.

Note on the IPv4-mapped case: `ip_network("127.0.0.1")` is an IPv4 network, and
`IPv6Address("::ffff:127.0.0.1") in <that network>` is `True` in CPython because
`IPv4Address.__contains__` maps the address. Step 1's last test pins this, and
Task 2's containment check relies on it.

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd backend && python -m pytest tests/test_trusted_proxies.py -v`
Expected: PASS

- [ ] **Step 7: Verify the env example test still passes**

Run: `cd backend && python -m pytest tests/test_env_example.py -v`
Expected: PASS

- [ ] **Step 8: Mutation-check both directions**

- Revert step 5's `except ValueError: continue` to `except ValueError: raise`.
  Run `tests/test_trusted_proxies.py`. Expected: FAIL on
  `test_unusable_entries_are_dropped_not_raised`.
- Restore, then delete the `entry == ""` skip. Run again. Expected: FAIL on
  `test_empty_yields_no_networks`.

- [ ] **Step 9: Commit**

```bash
git add backend/app/config.py backend/app/rate_limit.py backend/.env.example backend/tests/test_trusted_proxies.py
```

Commit message: `feat: add a trusted_proxies setting and its parser`

---

### Task 2: Gate the forwarded-header read on the socket peer

**Files:**
- Modify: `backend/app/rate_limit.py:6-21` (rewrite `_get_client_ip`)
- Modify: `backend/tests/test_rate_limit.py` (rewrite — see below)

**Interfaces:**
- Consumes: `_parse_trusted_proxies(value: str | None) -> list[IPv4Network | IPv6Network]` and `Settings.trusted_proxies: str` from Task 1.
- Produces: `_get_client_ip(request: Request) -> str` — unchanged signature. Every `@limiter.limit` in the app already depends on it and does not change.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_rate_limit.py` currently contains five tests that assert the
vulnerable behaviour — they expect `X-Forwarded-For` to win unconditionally, from
any peer. **Delete all five and replace the file** with a version whose
`_make_request` helper takes a `client_host` that defaults to a peer *outside*
every trusted set:

```python
"""The rate-limit identity is the socket peer unless the peer is a named proxy."""
import pytest
from unittest.mock import MagicMock

from app.config import Settings
from app.rate_limit import _get_client_ip, _parse_trusted_proxies


def _make_request(headers: dict = None, client_host: str = "198.18.0.7"):
    request = MagicMock()
    request.headers = {k.lower(): v for k, v in (headers or {}).items()}
    request.client.host = client_host
    return request
```

Then add these tests:

```python
def test_no_headers_uses_the_socket_peer():
    assert _get_client_ip(_make_request(), client_host="203.0.113.9") == "203.0.113.9"


def test_forwarded_header_is_ignored_from_an_untrusted_peer(monkeypatch):
    monkeypatch.setattr(Settings, "_trusted_networks", property(lambda s: []), raising=False)
    request = _make_request(headers={"X-Forwarded-For": "1.2.3.4"}, client_host="198.18.0.7")
    assert _get_client_ip(request) == "198.18.0.7"


def test_real_ip_is_also_ignored_from_an_untrusted_peer(monkeypatch):
    monkeypatch.setattr(Settings, "_trusted_networks", property(lambda s: []), raising=False)
    request = _make_request(headers={"X-Real-IP": "1.2.3.4"}, client_host="198.18.0.7")
    assert _get_client_ip(request) == "198.18.0.7"
```

Add three more that pin the trusted-peer path, using a helper that installs a
trusted set for the duration of the test:

```python
@pytest.fixture
def trusts_proxy(monkeypatch):
    monkeypatch.setattr(
        Settings, "_trusted_networks",
        property(lambda s: _parse_trusted_proxies("10.0.0.0/8")), raising=False,
    )
```

- `test_a_trusted_peer_gets_the_forwarded_for_header` — peer `10.1.2.3`,
  `X-Forwarded-For: 203.0.113.50` → `"203.0.113.50"`.
- `test_a_trusted_peer_gets_the_x_real_ip_header` — peer `10.1.2.3`,
  `X-Real-IP: 203.0.113.50` → `"203.0.113.50"`.
- `test_forwarded_for_wins_over_x_real_ip_for_a_trusted_peer` — both present,
  `X-Forwarded-For` wins (this ordering is already the established behaviour and
  `CRITICAL.md` records it as intentional).

And one for Review Focus item 4:

- `test_the_rightmost_untrusted_hop_is_chosen` — peer `10.1.2.3` (trusted),
  `X-Forwarded-For: 1.2.3.4, 203.0.113.50`. Expected: `"203.0.113.50"`, the
  address the trusted proxy actually observed — **not** `"1.2.3.4"`. Explain in
  the test docstring that taking the leftmost re-creates the original bypass for
  any proxy that appends rather than overwrites.

And one for Review Focus item 5:

- `test_a_present_but_empty_header_falls_through_to_the_peer` —
  `headers={"X-Forwarded-For": ""}`, peer `10.1.2.3` → `"10.1.2.3"`.

And one for Review Focus item 1:

- `test_an_ipv4_mapped_ipv6_peer_matches_its_ipv4_trusted_entry` — trusted set
  is `127.0.0.1`, peer is `::ffff:127.0.0.1`, `X-Forwarded-For: 203.0.113.50`
  → `"203.0.113.50"`. Without this, localhost is untrusted in development and
  the header is silently dropped.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_rate_limit.py -v`
Expected: FAIL. The untrusted-peer tests fail because `_get_client_ip` still
returns the header, and `Settings` has no `_trusted_networks` attribute.

- [ ] **Step 3: Add the property to `Settings` in `backend/app/config.py`**

```python
    @property
    def _trusted_networks(self) -> list:
        """The parsed TRUSTED_PROXIES networks.

        Deliberately recomputed rather than cached: pydantic v2 forbids assigning
        an undeclared attribute on a model instance, so the obvious
        `self._cache = ...` memo raises `ValueError` at runtime. Parsing a short
        string into a handful of networks costs microseconds on a path that is
        already doing network I/O, so do not add the cache back without a
        `PrivateAttr`.

        The tests monkeypatch this property, which is why it is a property and
        not a module-level read of `settings`.
        """
        from app.rate_limit import _parse_trusted_proxies

        return _parse_trusted_proxies(self.trusted_proxies)
```

Import `_parse_trusted_proxies` inside the method body, not at module scope —
`rate_limit.py` imports `slowapi`, and `config.py` is imported by tests that must
stay cheap, so a module-level import would drag the rate limiter into every test.

- [ ] **Step 4: Rewrite `_get_client_ip` in `backend/app/rate_limit.py`**

Keep the signature `_get_client_ip(request: Request) -> str`. Replace the body so
it:

1. Reads `peer = request.client.host` (falling back to `get_remote_address(request)`
   if `client` is `None`).
2. Returns `peer` immediately unless `peer` falls inside one of
   `settings._trusted_networks`. Use `ip_address(peer)` and compare with the `in`
   operator, wrapped in `try/except ValueError` so a non-IP peer string falls back
   to itself rather than raising.
3. Only then reads `X-Forwarded-For`, splits on `,`, strips each element, and
   returns the **rightmost** element whose address is not itself inside a trusted
   network — falling back to the rightmost element if every hop is trusted.
4. Returns `""` for a header that is present but empty rather than indexing into
   an empty split.
5. Otherwise tries `X-Real-IP` and returns it stripped, and finally returns `peer`.

Replace the existing docstring entirely. The current one describes the behaviour
being removed, and leaving it would be a comment that lies. The new docstring
should state that forwarded headers are untrusted input that only become the
identity when the socket peer is an operator-named proxy.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_rate_limit.py -v`
Expected: PASS

- [ ] **Step 6: Mutation-check both directions**

- Revert step 4 to the old body (header wins unconditionally). Run again.
  Expected: FAIL on `test_forwarded_header_is_ignored_from_an_untrusted_peer`.
- Change the hop selection from rightmost-untrusted back to `split(",")[0]`.
  Expected: FAIL on `test_the_rightmost_untrusted_hop_is_chosen`.
- Remove the empty-string guard from step 4.4. Expected: FAIL on
  `test_a_present_but_empty_header_falls_through_to_the_peer`.
- Remove the `ip_address` containment check and compare peer strings directly.
  Expected: FAIL on
  `test_an_ipv4_mapped_ipv6_peer_matches_its_ipv4_trusted_entry`.

- [ ] **Step 7: Run the full backend suite**

Run: `cd backend && python -m pytest tests/ -v`
Expected: PASS, no new failures. It must still complete in a few seconds; if it
suddenly takes tens of seconds, something has started reaching the network.

- [ ] **Step 8: Commit**

```bash
git add backend/app/rate_limit.py backend/app/config.py backend/tests/test_rate_limit.py
```

Commit message: `fix: only trust forwarded headers from a named proxy`

---

### Task 3: Prove the bound holds through the real app, and warn the operator

**Files:**
- Create: `backend/tests/test_rate_limit_bypass.py`
- Modify: `backend/app/main.py` (startup warning)
- Modify: `AGENTS.md` (the `rate_limit.py` entry)

**Interfaces:**
- Consumes: `_get_client_ip` from Task 2 and the existing offline fixtures in `backend/tests/conftest.py`.
- Produces: an integration test that would fail against the pre-fix code; a startup warning naming the exact env var to set.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_rate_limit_bypass.py`:

```python
"""The bound must hold through the real app, not just the key function.

This is the test the audit's validation plan asked for. Every request below
carries a fresh X-Forwarded-For, so a limiter keyed on the header sees a new
principal each time and never engages.
"""
```

Use the `TestClient`/`AsyncClient`+`ASGITransport` pattern already in
`backend/tests/test_rate_limit_policy.py`, and post **six** requests to
`POST /api/match-resume` (the route with the tightest limit, `3/minute`) — one
more than the limit allows. Mock the AI boundary via the autouse fixtures in
`conftest.py`; this run must not reach OpenRouter.

Two tests:

- `test_rotating_the_forwarded_header_does_not_reset_the_budget` — six requests,
  each with a distinct `X-Forwarded-For`. **Expected: at least one 429**, and
  specifically that the request after the third is refused. Assert on the
  presence of a 429 in the status sequence rather than an exact index, so the
  test stays honest about slowapi's window boundary.
- `test_without_the_header_the_same_budget_still_applies` — the control. Six
  requests, no forwarded header. Expected: the same 429 pattern. A test that only
  passes when the bypass exists would prove nothing; this one is what makes the
  first test mean something.

Both tests must call `_reset_rate_limiter` (or whatever the conftest fixture is
named) so they do not inherit each other's window. `AGENTS.md` records that the
limiter's memory storage is process-wide and this exact collision once turned an
unrelated test into a 429.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_rate_limit_bypass.py -v`
Expected: FAIL — the first test finds six 200s and no 429, which is exactly the
vulnerability.

- [ ] **Step 3: Make them pass**

No production change is expected; Task 2's fix should turn them green. Run again
and confirm PASS. If the first still fails, Task 2's gate is not actually
reached from the app — investigate rather than relaxing the assertion.

- [ ] **Step 4: Mutation-check both directions**

- Revert Task 2's production change. Run again. Expected: FAIL on the first
  test, PASS on the control. Both halves matter: a control that fails alongside
  its test would mean the test is not measuring the bypass.
- Then verify the overcorrection: hardcode the key to `request.client.host` while
  leaving `TRUSTED_PROXIES` set, and confirm the two trusted-peer tests in
  `test_rate_limit.py` fail. A fix that ignores the header even behind a real
  proxy passes the bypass test and is wrong.

- [ ] **Step 5: Write the failing test for the startup warning**

The warning is Review Focus item 2: with `TRUSTED_PROXIES` blank behind a proxy,
every caller shares one bucket. That is fail-closed and correct, but it is the
failure most likely to surprise the operator, so it must say so out loud rather
than being discovered as an unexplained 429.

Add to `backend/tests/test_rate_limit_bypass.py`:

```python
def test_startup_warns_when_no_proxy_is_trusted(caplog, monkeypatch):
    """Blank TRUSTED_PROXIES collapses every caller into one bucket."""
```

Monkeypatch `settings.trusted_proxies` to `""`, call the logging helper directly
with a `caplog` context, and assert the emitted record contains both
`TRUSTED_PROXIES` and the word `proxy`. Assert on those two substrings rather
than the full sentence, so rewording the message is not a test failure while
still stopping the warning from being gutted into something useless.

Pin the negative too: with `trusted_proxies` set to a non-blank value, the helper
must emit nothing. A warning that fires unconditionally is noise, and it trains
the operator to ignore the one time it matters.

- [ ] **Step 6: Implement the warning in `backend/app/main.py`**

Put the check in the app's startup path, before it begins serving, and route it
through a small module-level helper — `_warn_if_no_trusted_proxies()` — so
Step 5's test can call it without starting the app.

Log a single WARNING when `settings.trusted_proxies` is blank, naming the
consequence and the fix in the message itself:

> `TRUSTED_PROXIES is empty — forwarded headers are ignored and every caller
> shares one rate-limit bucket. If this service is behind a proxy, set
> TRUSTED_PROXIES to the proxy's IP ranges or the per-caller limits will not
> apply.`

One line, at startup, not per request.

- [ ] **Step 7: Update the `AGENTS.md` entry for `backend/app/rate_limit.py`**

That entry currently describes the bypass as present. Rewrite it to describe the
gate, and cross-reference `docs/security-audit-2026-10-14.md`. Keep the note that
uvicorn's `ProxyHeadersMiddleware` mutates `scope["client"]` and not
`scope["headers"]` — that is why this code cannot delegate the decision to
uvicorn, and it will be the first thing a future reader tries.

Also extend the `backend/app/core/auth.py` entry: it claims the loss is "bounded
instead" by rate limits, which is now true, but the bound is only as good as the
proxy configuration. Note the dependency rather than leaving the claim unqualified.

- [ ] **Step 8: Run the full backend suite**

Run: `cd backend && python -m pytest tests/ -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/tests/test_rate_limit_bypass.py backend/app/main.py AGENTS.md
```

Commit message: `test: prove the rate-limit bound holds through the app`

---

## After this plan

Finding 1 is closed at source. Two follow-ups this plan deliberately does not
absorb, because they are separate changes with separate reviews:

- **Finding 2** (blocking DNS lookups on the event loop) is a one-line fix —
  `asyncio.to_thread` around `verify_emails_in_text` plus a count cap — but it
  belongs to `email_verifier.py`, not `rate_limit.py`.
- **`TRUSTED_PROXIES` must be set in the deployed environment.** The code
  defaults to trusting nothing, which is correct but means the deployed limits
  will collapse into a shared bucket until this is configured. That is an
  operator action and it is not a code change.