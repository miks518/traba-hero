"""One employer query, and what may no longer be built in code.

There was a pair - `registration certificate` and `reviews complaints` - built
here from the employer name. Both are gone: they starved each other, and a
single `"<company> company or employer"` returns the employer's own pages, a
PESO listing and a job board post in one result set.

Everything the pair was guarding against is still guarded, but by a different
party. `scam` and `fraud` stay out of a query because a query carrying a
conclusion returns pages that appear to corroborate it.

That rule used to live in the scan prompts alone, with the queries model-authored
and unfiltered in code. `search_query_is_safe` in `search_planner.py` drops a
query carrying a conclusion word before it is ever issued — and since the
verdict-procedure work it runs **in every mode**: the adaptive planner applies
it to the queries it chooses, the fixed mode applies it to the scan model's
proposals where they are issued (before the cap), and the agent's tool calls
are filtered at the parser (`agent_protocol.parse_tool_calls`). The earlier
record — that in `fixed` mode the prompt sentence was the only control — is
amended rather than left to contradict the code.

The tombstone below exists because "no filter" was a decision a future reader would
otherwise mistake for an oversight. The filter is now universal, and the class
`TestTheFixedModeFilterIsACodeControl` is what pins it.

`build_scheme_queries` and its attribute table are deleted outright. The model
proposes its own searches now, so anything that rebuilt them from attributes
would be a second, competing source of queries - and a stale one.
"""

import json

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.search import build_queries, merge_results, SearchResult



def _result(url, score=0.5, title="t", snippet="s"):
    return SearchResult(title=title, url=url, snippet=snippet, score=score)


class TestMergingTwoResultSets:
    def test_keeps_the_higher_scoring_copy_of_a_duplicated_url(self):
        merged = merge_results(
            [_result("https://example.ph/a", 0.2)],
            [_result("https://example.ph/a", 0.9)],
        )

        assert len(merged) == 1
        assert merged[0].score == 0.9

    def test_a_tracking_parameter_does_not_make_a_duplicate_look_distinct(self):
        """The same page reached by two queries is one piece of evidence.

        Every result is prompt text competing for a reasoning model's budget, so
        a page listed twice is paid for twice while telling the model nothing
        new.
        """
        merged = merge_results(
            [_result("https://example.ph/acme")],
            [_result("https://example.ph/acme?ref=jobstreet", 0.9)],
        )

        assert len(merged) == 1

    def test_a_trailing_slash_does_not_make_a_duplicate_look_distinct(self):
        merged = merge_results(
            [_result("https://example.ph/acme")],
            [_result("https://example.ph/acme/")],
        )

        assert len(merged) == 1

    def test_distinct_pages_are_all_kept(self):
        merged = merge_results(
            [_result("https://example.ph/a"), _result("https://example.ph/b")],
            [_result("https://example.ph/c")],
        )

        assert len(merged) == 3

    def test_the_merged_order_puts_the_strongest_results_first(self):
        merged = merge_results(
            [_result("https://example.ph/low", 0.1)],
            [_result("https://example.ph/high", 0.9), _result("https://example.ph/mid", 0.5)],
        )

        assert [r.url for r in merged] == [
            "https://example.ph/high", "https://example.ph/mid", "https://example.ph/low",
        ]

    def test_the_cap_trims_the_tail_not_the_top(self):
        """Trimming by score matters: the tail is what the budget cannot hold."""
        merged = merge_results(
            [_result(f"https://example.ph/{i}", score=i / 100) for i in range(10)],
            [],
            cap=4,
        )

        assert len(merged) == 4
        assert merged[0].url == "https://example.ph/9"

    def test_merging_nothing_yields_nothing(self):
        assert merge_results([], []) == []

    def test_a_missing_url_is_not_treated_as_a_duplicate_of_another_missing_url(self):
        """Two results with no URL are two results, not one collapsed pair."""
        merged = merge_results([_result(""), _result("")], [])

        assert len(merged) == 2


class TestTheEmployerQuery:
    def test_there_is_exactly_one(self):
        """One request, so the employer lookup costs one credit."""
        assert build_queries("Tanika") == ["Tanika company or employer"]

    def test_the_or_covers_both_spellings_of_the_name(self):
        """A small business is often only findable under one of the two.

        The query reads as a boolean, so a company writing itself "Tanika
        Company", "Tanika Employer" or neither is matched either way. A wrong
        guess at the suffix is a query that returns nothing about the employer
        every other check is about.
        """
        query = build_queries("Tanika")[0].lower()

        assert "company" in query
        assert "employer" in query

    def test_the_name_is_used_verbatim(self):
        """The legal name is how filings, PESO listings and legal pages title
        themselves, so stripping the suffix left the distinctive part competing
        against a brand and its franchisees."""
        assert build_queries("Jollibee Foods Corporation") == [
            "Jollibee Foods Corporation company or employer"
        ]

    @pytest.mark.parametrize(
        "name",
        ["Tanika Corporation", "Tanika Corp", "Tanika Inc", "Tanika Co", "Tanika LLC"],
    )
    def test_every_supported_suffix_survives(self, name):
        assert build_queries(name)[0].startswith(name)

    def test_the_philippines_is_no_longer_appended_to_the_query(self):
        """The suffix was the same signal the request already carries.

        `country` on the search request biases ranking toward Philippine results,
        so appending "Philippines" to every query spent characters without
        adding reach.
        """
        assert not any("philippines" in q.lower() for q in build_queries("Tanika"))


class TestThePhilippinesIsNowCarriedByTheRequest:
    """The overcorrection of deleting the suffix.

    Removing it from the query text left `TAVILY_COUNTRY` as the only geographic
    signal. If a deployment ever sets it blank, nothing anchors these queries to
    the Philippines at all - and that failure is invisible, because the search
    still succeeds and returns results from somewhere.

    `country` is a *boost*, not a filter, which is also why removing it does not
    lose the local job boards and PESO listings the query targets: it widens the
    result set rather than restricting it.
    """

    def _body_sent(self, monkeypatch, country):
        import app.services.search as mod
        from tests.test_search import FakeResponse

        captured = {}

        def fake_post(url, json=None, timeout=None, headers=None):
            captured.update(json or {})
            return FakeResponse({"results": []})

        monkeypatch.setattr(mod.settings, "tavily_api_key", "tvly-test")
        monkeypatch.setattr(mod.settings, "search_provider", "tavily")
        monkeypatch.setattr(mod.settings, "tavily_country", country)
        monkeypatch.setattr(mod.httpx, "post", fake_post)
        mod.search(build_queries("Tanika")[0], 5)
        return captured

    def test_the_country_boost_is_sent_on_every_request(self, monkeypatch):
        # Pinned rather than read from the environment: the default is not the
        # subject here, the request shape is.
        assert self._body_sent(monkeypatch, "philippines")["country"] == "philippines"

    def test_a_blank_country_is_dropped_rather_than_sent_as_empty(self, monkeypatch):
        """`country: ""` is a request the provider may reject, which would turn
        an operator blanking a config into a reported lookup failure."""
        assert "country" not in self._body_sent(monkeypatch, "   ")

    def test_the_query_itself_carries_no_country(self, monkeypatch):
        """Both halves of the change, asserted together: the geography moved
        from the query text to the request."""
        body = self._body_sent(monkeypatch, "philippines")

        assert "philippines" not in body["query"].lower()
        assert body["country"] == "philippines"


class TestTheDomainScopeIsAPreferenceNotAFilter:
    """`include_domains` is sent, and only ever in `prefer` mode.

    Tavily defaults `include_domains_mode` to `restrict`: results come *only*
    from the listed domains. That is the exact behaviour the comment above this
    class refused to accept, because it discards the JobStreet, Indeed PH and
    PESO pages the country boost exists to surface. `prefer` boosts the listed
    domain and still searches the rest of the web, which is the same kind of
    lever as `country` — so both can be sent on one request, and neither
    excludes anything.

    Asserted on the request body because this spends a credit per call and the
    mode is the only thing standing between a boost and a filter.
    """

    def _body_sent(self, monkeypatch, scope):
        import app.services.search as mod
        from tests.test_search import FakeResponse

        captured = {}

        def fake_post(url, json=None, timeout=None, headers=None):
            captured.update(json or {})
            return FakeResponse({"results": []})

        monkeypatch.setattr(mod.settings, "tavily_api_key", "tvly-test")
        monkeypatch.setattr(mod.settings, "search_provider", "tavily")
        monkeypatch.setattr(mod.httpx, "post", fake_post)
        mod.search(build_queries("Tanika")[0], 5, scope)
        return captured

    def test_a_scope_is_sent_in_prefer_mode(self, monkeypatch):
        body = self._body_sent(monkeypatch, ["ched.gov.ph"])

        assert body["include_domains"] == ["ched.gov.ph"]
        assert body["include_domains_mode"] == "prefer"

    def test_no_scope_means_neither_key_is_sent(self, monkeypatch):
        """Declaring an intent to boost nothing is a request for nothing."""
        body = self._body_sent(monkeypatch, None)

        assert "include_domains" not in body
        assert "include_domains_mode" not in body

    def test_a_scope_coexists_with_the_country_boost(self, monkeypatch):
        """The whole reason `prefer` was chosen over `restrict`.

        Two boosts on one request is fine. A boost and a filter is not.
        """
        body = self._body_sent(monkeypatch, ["ched.gov.ph"])

        assert body["country"] == "philippines"
        assert body["include_domains_mode"] == "prefer"

    def test_a_scope_is_normalised_before_it_is_sent(self, monkeypatch):
        """`www.` and a protocol are the same domain; two spellings would be two
        entries and a half-applied boost."""
        body = self._body_sent(monkeypatch, ["https://www.ched.gov.ph/"])

        assert body["include_domains"] == ["ched.gov.ph"]

    def test_a_subdomain_scope_is_reduced_to_the_registrable_domain(self, monkeypatch):
        """`hr.ched.gov.ph` and `ched.gov.ph` are one employer, and scoping to the
        former would exclude the latter."""
        body = self._body_sent(monkeypatch, ["hr.ched.gov.ph"])

        assert body["include_domains"] == ["ched.gov.ph"]

    def test_a_wildcard_is_dropped_rather_than_sent(self, monkeypatch):
        """The provider rejects wildcards with a 400, and a 400 here reads as a
        failed lookup rather than a malformed scope."""
        body = self._body_sent(monkeypatch, ["*.ched.gov.ph"])

        assert "include_domains" not in body

    def test_a_scope_with_a_path_is_dropped(self, monkeypatch):
        body = self._body_sent(monkeypatch, ["ched.gov.ph/careers"])

        assert "include_domains" not in body

    def test_an_unusable_scope_does_not_fail_the_search(self, monkeypatch):
        """A scope is an optimisation. Losing it costs recall, nothing else."""
        body = self._body_sent(monkeypatch, ["not a domain"])

        assert body["query"]
        assert "include_domains" not in body


class TestTheSchemeQueryBuilderIsDeleted:
    """Tombstones. A function left in the module is a trap for the next reader.

    The scan model proposes its own searches now. A surviving builder would be a
    second source of queries, and nothing would call it - which is exactly the
    state commit 413a2cd deleted a different feature for.
    """

    def test_the_builder_is_gone(self):
        import app.services.search as search_module

        assert not hasattr(search_module, "build_scheme_queries")

    def test_the_attribute_table_is_gone(self):
        """It existed to answer "what can a search check", which is now the
        model's question rather than the module's."""
        import app.services.search as search_module

        assert not hasattr(search_module, "CHECKABLE_ATTRIBUTES")

    def test_the_country_suffix_helper_is_gone(self):
        """`country` carries the geography. A suffix helper left here would be
        someone re-adding the duplicate signal."""
        import app.services.search as search_module

        assert not hasattr(search_module, "_with_country")

    def test_the_prose_squeezer_is_gone(self):
        """It reduced an attribute value to a query fragment. Model-authored
        queries are already written as queries."""
        import app.services.search as search_module

        assert not hasattr(search_module, "_squeeze")


transport = ASGITransport(app=app)


class TestTheFixedModeFilterIsACodeControl:
    """A prompt sentence is not a control.

    The record said that in the shipped `fixed` mode the scan prompt's rule was
    the only thing standing between a model query and the search engine. That
    record described the code truthfully, and the code was wrong; the code is
    changed here and the record is amended with it, not left to contradict it.
    The same refusal the adaptive planner's queries answer to now answers the
    fixed mode's model queries.
    """

    AI = json.dumps({
        "checks": [
            {"category": "Company Existence", "status": "confirmed",
             "finding": "A business by that name operates.",
             "source_title": "Acme", "source_url": "https://example.ph/acme"},
        ],
        "evidence": [],
        "report": "The results show a registered business.",
        "recommendation": "Ask them to confirm the address in writing.",
    })

    async def _verify(self, model_queries):
        """The house pattern from test_verify.py: fake the search and the chat
        at the router boundary, post to the endpoint, count what was issued."""
        from unittest.mock import patch as _patch
        from app.services.search import SearchOutcome
        from tests.test_verify import _cycled

        hits = SearchOutcome(
            results=[SearchResult("Acme", "https://example.ph/acme", "s", 0.8)], ok=True
        )

        with (
            _patch("app.routers.scan.search", side_effect=_cycled([hits])) as search,
            _patch("app.routers.scan.chat", return_value=self.AI),
        ):
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.post("/api/verify", json={
                    "company_name": "Acme Corp",
                    "job_summary": "Developer at Acme Corp",
                    "search_queries": model_queries,
                })
        return resp, search

    @pytest.mark.asyncio
    async def test_a_conclusion_word_in_a_model_query_is_refused(self):
        resp, search = await self._verify(["Tanika scam reports"])
        assert resp.status_code == 200
        issued = [c.args[0] for c in search.call_args_list]
        assert issued == ["Acme Corp company or employer"]

    @pytest.mark.asyncio
    async def test_a_safe_model_query_still_runs_beside_the_employer_query(self):
        resp, search = await self._verify(["Acme Corp branch"])
        issued = [c.args[0] for c in search.call_args_list]
        assert issued == ["Acme Corp company or employer", "Acme Corp branch"]

    @pytest.mark.asyncio
    async def test_a_refused_query_consumes_no_slot(self):
        """The filter runs before the cap: a refused query must not spend one
        of the two slots a safe query could have used."""
        resp, search = await self._verify(
            ["Tanika scam reports", "Acme Corp branch", "Acme Corp permit"]
        )
        issued = [c.args[0] for c in search.call_args_list]
        assert issued == [
            "Acme Corp company or employer", "Acme Corp branch", "Acme Corp permit",
        ]
