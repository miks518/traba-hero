"""Two queries per verification, and what they may not become.

The single query was `"<company> Philippines"`, which ranks the employer's own
site and job boards first. Those pages prove the company exists and almost never
state a registration number, so a PESO or SEC listing sat below the fold of the
result list and "Official Registration" was starved by ranking rather than by
absence. Raising `max_results` cannot fix that; the query only asks for one
category's worth of evidence.

A second query for registration fixes the ranking. It must not become a way to
ask the retrieval engine for a verdict, so the constraints below are the
load-bearing part of this change, not the query string.
"""

import pytest

from app.services.search import build_queries, build_scheme_queries, merge_results, SearchResult


class TestTheQuerySet:
    def test_there_are_two_queries(self):
        queries = build_queries("Jollibee")

        assert len(queries) == 2
        assert all(q.endswith("Philippines") for q in queries)

    def test_the_two_queries_target_registration_and_reputation(self):
        queries = [q.lower() for q in build_queries("Jollibee")]

        assert "registration" in queries[0]
        assert "certificate" in queries[0]
        assert "reviews" in queries[1]

    def test_the_registration_query_names_a_document_not_a_registry(self):
        """"Registration certificate" is a document noun, which is the rule.

        The ban is on naming a *conclusion* (`scam`) or a *specific regulator*
        (SEC, which would starve the DTI/PEZA/BOI/LGU registrants the category
        was widened to include). A certificate is the artefact itself, and
        naming the artefact ranks filings higher than a bare "registration"
        would — a PESO page or an SEC listing is titled after the document.
        """
        for query in build_queries("Acme Corporation"):
            for registry in ("sec", "dti", "peza", "boi"):
                assert registry not in query.lower(), registry

    def test_the_reputation_query_carries_both_terms(self):
        """`reviews complaints`, not one or the other.

        A review page and a published complaint are different documents: the
        first is a rating the employer can respond to, the second is an adverse
        record. Searching for only one misses the other, and the category the
        panel reports is about what a result *states*.
        """
        reputation = build_queries("Jollibee")[1].lower()

        assert "reviews" in reputation
        assert "complaints" in reputation

    def test_the_registration_query_never_names_one_registry(self):
        """Naming SEC alone reintroduces the bug the category rename fixed.

        `Official Registration` exists because a company holding a DTI, PEZA,
        BOI, or LGU business permit was being reported as unregistered by an
        SEC-only check. A query that says "SEC" would starve exactly those
        registrants the category was widened to include.
        """
        for query in build_queries("Acme Corporation"):
            assert "sec" not in query.lower(), query
            assert "dti" not in query.lower(), query
            assert "peza" not in query.lower(), query

    def test_no_query_uses_the_accusatory_terms(self):
        """The ban is on asking retrieval for a verdict, not on querying at all.

        `scam` and `fraud` name a conclusion. A query carrying one biases
        retrieval toward adverse results about a named real company, so the
        results look like corroboration of the accusation the query already
        embedded. `Company Reputation` exists to report what a *result* states,
        never what the query asked for.

        `reviews` and `complaints` were added to the queries deliberately and
        are therefore allowed here. That is a trade the project owner made with
        the risk in front of them, not an oversight: those terms do surface
        employee experience and published complaint pages that a neutral query
        never reaches. The residual exposure is aggregator pages that re-publish
        complaint text against a scraped company name, which is why the prompt
        still requires a result to name the same entity and why `red` requires
        a source. Do not add `scam` or `fraud` to this list's complement.
        """
        banned = ("scam", "fraud")
        for query in build_queries("Acme Corporation"):
            for word in banned:
                assert word not in query.lower(), f"{word!r} in {query!r}"

    def test_company_existence_is_no_longer_its_own_query(self):
        """Existence is now inferred from the other two searches.

        Traded deliberately: a company with a rating page, a filing, or a
        published complaint is found by those queries, and the existence check
        is redundant against them. The cost is that an employer with no review
        profile and no filing is found by neither, and reports yellow on
        existence — a real regression for the smallest employers, which is
        exactly who this product is for.
        """
        queries = build_queries("Acme Corporation")

        # Neither query is the plain existence lookup it used to be, so
        # existence is now judged from the merged list rather than asked for.
        assert not any(q == "Acme Corporation Philippines" for q in queries)

    def test_reputation_is_covered_by_a_query(self):
        queries = build_queries("Acme Corporation")

        assert any("reviews" in q.lower() for q in queries)

    def test_registration_is_still_covered(self):
        queries = build_queries("Acme Corporation")

        assert any("registration" in q.lower() for q in queries)

    def test_both_queries_keep_the_employer_name_verbatim(self):
        """Only the axis term and the country are appended to the name.

        The scan states the employer once, and verification looks it up. Nothing
        between the two may rewrite the distinctive part, because every rewrite
        is a chance to search a different company than the one named.
        """
        for query in build_queries("Silvergreen Manpower Services Corporation"):
            assert query.startswith("Silvergreen Manpower Services Corporation")

    def test_a_name_already_naming_the_country_is_not_anchored_twice(self):
        for query in build_queries("Jollibee Philippines"):
            assert query.lower().count("philippines") == 1, query

    def test_the_legal_name_survives_into_every_query(self):
        """The suffix is kept, and this is deliberate.

        It used to be stripped, on the reasoning that a generic legal form
        dilutes a rare name. In practice it does the opposite for a Philippine
        employer: the filing, the PESO listing, and the company's own legal pages
        are all titled with the *legal* name, while stripping it left the
        distinctive part competing against a brand, its franchisees, and
        unrelated products sharing the word. "Jollibee Foods" is a worse query
        than "Jollibee Foods Corporation".

        Recorded in AGENTS.md as a reversal, not an oversight.
        """
        for query in build_queries("Jollibee Foods Corporation"):
            assert "corporation" in query.lower(), query

    def test_every_supported_suffix_survives(self):
        for suffix in ("Corporation", "Corp", "Corp.", "Inc", "Incorporated", "Co", "LLC"):
            name = f"Jollibee Foods {suffix}"
            for query in build_queries(name):
                assert query.startswith(name), f"{suffix!r} was altered in {query!r}"

    def test_a_name_that_is_only_a_suffix_is_still_searchable(self):
        """'Corporation' alone used to strip to nothing.

        It cannot now, but the guard stays: a name that reduced to the geographic
        term alone would return results about any company.
        """
        for name in ("Corporation", "Inc", "Co"):
            for query in build_queries(name):
                assert query.startswith(name), f"{name!r} became {query!r}"


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


class TestSchemeQueries:
    """Queries come from what the posting states, never from its labels.

    A model's `high` label is a characterisation; using it as a query term puts
    the accusation inside the query, and a query carrying a conclusion makes its
    own results look like corroboration. Only checkable attributes qualify, and
    only when the posting actually stated them.
    """

    def test_no_attributes_means_no_queries(self):
        assert build_scheme_queries({}, "Acme") == []

    def test_absent_attributes_are_not_queried_either(self):
        """`None` is "the posting stated nothing", the same claim as `{}`.

        The verification request carries whatever the scan produced, and a scan
        that raised no attributes at all must not turn into an `AttributeError`
        halfway through the verification stream.
        """
        assert build_scheme_queries(None, "Acme") == []

    def test_no_employer_name_means_no_query(self):
        """A detail with no employer attached is a place, not an impersonation.

        "Maingate Terminal recruitment Philippines" searches a bus terminal. The
        whole point of these queries is to find pages that pair a claim with the
        company claiming it, and there is no company to pair with.
        """
        assert build_scheme_queries({"LOCATION": "Maingate Terminal"}, "") == []
        assert build_scheme_queries({"LOCATION": "Maingate Terminal"}, "   ") == []

    def test_a_location_the_posting_stated_produces_a_query(self):
        queries = build_scheme_queries(
            {"LOCATION": "Maingate Terminal"}, "Tanika"
        )
        # The employer name and the stated detail, verbatim, anchored to the
        # country exactly as `build_queries` anchors its own.
        assert queries == ["Tanika Maingate Terminal Philippines"]

    def test_the_query_carries_no_category_word(self):
        """The trailing term is the country, not `recruitment`.

        `build_queries` appends a *document* noun (`registration certificate`,
        `reviews complaints`) because it is asking for a category's evidence. A
        scheme query is not asking for a category — it is asking for pages that
        mention this employer together with this detail — so it appends nothing
        but the country anchor. `recruitment` would steer retrieval toward job
        boards, which is the same category bias the employer queries avoid.
        """
        queries = build_scheme_queries({"LOCATION": "Maingate Terminal"}, "Tanika")

        assert queries == ["Tanika Maingate Terminal Philippines"]
        assert "recruitment" not in queries[0].lower()

    def test_the_poster_prose_is_stripped_from_the_detail(self):
        """Only the searchable part of a stated detail survives into the query.

        The connector words are the poster's sentences, not the place, and they
        dilute the query without adding a term the index will use.
        """
        queries = build_scheme_queries(
            {"LOCATION": "our Robinsons Starmills branch in Cabatuan"}, "Tanika"
        )

        assert queries == ["Tanika Robinsons Starmills in Cabatuan Philippines"]

    def test_a_detail_stated_twice_produces_one_query(self):
        """Two attributes naming the same place is one question, not two.

        A posting that gives a LOCATION and a MEETING_SPOT which are the same
        supermarket must not spend two credits asking the same thing twice.
        """
        queries = build_scheme_queries(
            {
                "LOCATION": "Waltermart Mabalacat",
                "MEETING_SPOT": "Waltermart Mabalacat",
            },
            "Tanika",
        )

        assert queries == ["Tanika Waltermart Mabalacat Philippines"]

    def test_pay_and_role_are_never_queried(self):
        # A salary figure is not corroborated or refuted by a web search, so a
        # query for one spends a credit and learns nothing.
        queries = build_scheme_queries(
            {"PAY": "26,000 monthly", "ROLE": "crew"}, "Tanika"
        )
        assert queries == []

    def test_a_missing_location_produces_nothing(self):
        # The case a naive "one query per attribute" implementation gets wrong:
        # it spends a credit searching for something the posting never said.
        #
        # The length and content assertions matter as much as the ban: `all(...)`
        # over an empty list is vacuously true, so a build_scheme_queries that
        # returned [] for everything would otherwise pass this.
        queries = build_scheme_queries({"CONTACT_METHOD": "personal Gmail"}, "Tanika")

        assert len(queries) == 1
        assert "gmail" in queries[0].lower()
        assert all("location" not in q.lower() for q in queries)

    def test_a_placeholder_attribute_is_not_queried(self):
        queries = build_scheme_queries(
            {"LOCATION": "Not stated"}, "Tanika"
        )
        assert queries == []

    @pytest.mark.parametrize(
        "placeholder", ["", "  ", "none", "N/A", "NA", "not stated", "Not Mentioned", "unknown", "-"]
    )
    def test_every_placeholder_shape_is_skipped(self, placeholder):
        """A surviving placeholder becomes a query, and a query for "none" is a
        credit spent to learn nothing.

        The scan's own parser drops only the exact string "not stated", so the
        backend cannot rely on the model having used that one spelling.
        """
        assert build_scheme_queries({"LOCATION": placeholder}, "Tanika") == []

    def test_the_cap_is_three(self):
        queries = build_scheme_queries(
            {
                "LOCATION": "Pampanga",
                "CONTACT_METHOD": "personal Gmail",
                "MEETING_SPOT": "Waltermart Mabalacat",
            },
            "Tanika",
        )
        assert len(queries) == 3

    def test_the_cap_holds_when_more_attributes_than_the_cap_are_stated(self):
        """A detailed posting must not cost more to check than a sparse one.

        Only three attribute names are checkable today, so the cap is currently
        unreachable from `CHECKABLE_ATTRIBUTES` alone. It stays as the guard for
        whoever adds a fourth: a fourth checkable attribute without a cap would
        silently raise the price of every verification.
        """
        queries = build_scheme_queries(
            {
                "LOCATION": "Pampanga",
                "CONTACT_METHOD": "personal Gmail",
                "MEETING_SPOT": "Waltermart Mabalacat",
                "SCHEDULE": "immediately",
                "AGE_RANGE": "20-30",
            },
            "Tanika",
        )

        assert len(queries) == 3

    def test_the_company_name_is_used_verbatim(self):
        # No suffix strip: a filing and a store locator are titled with the legal
        # name, and stripping it searches a different company than the one named.
        queries = build_scheme_queries({"LOCATION": "Quezon City"}, "Jollibee Foods Corporation")
        assert "Jollibee Foods Corporation" in queries[0]

    def test_every_query_starts_with_the_employer_name(self):
        """The name leads every query, not just the first.

        A detail alone is searchable — "Waltermart Mabalacat" is a supermarket,
        not an impersonation of Tanika — so a query without the name returns
        pages that have nothing to do with the posting.
        """
        queries = build_scheme_queries(
            {
                "LOCATION": "Pampanga",
                "CONTACT_METHOD": "personal Gmail",
                "MEETING_SPOT": "Waltermart Mabalacat",
            },
            "Jollibee Foods Corporation",
        )

        assert len(queries) == 3
        for query in queries:
            assert query.startswith("Jollibee Foods Corporation"), query

    def test_an_employer_name_already_naming_the_country_is_not_anchored_twice(self):
        queries = build_scheme_queries({"LOCATION": "Quezon City"}, "Tanika Philippines")

        assert all(q.lower().count("philippines") == 1 for q in queries), queries

    def test_no_query_carries_a_conclusion(self):
        banned = ("scam", "fraud", "fake", "illegal", "criminal")
        queries = build_scheme_queries(
            {"LOCATION": "Pampanga", "MEETING_SPOT": "bus terminal"},
            "Tanika",
        )
        assert queries
        for q in queries:
            for word in banned:
                assert word not in q.lower()


class TestTheConstantHasOneHome:
    """`CHECKABLE_ATTRIBUTES` is defined once, in the module that consumes it.

    Task 1 defined it in `lm_client.py`, where nothing read it — and where it
    could not have been used honestly, because the parser there keeps `PAY` and
    `COMPANY` as reported attributes. The parser's set answers "what did the
    posting state", this one answers "what can a search check", and a name
    shared between two different questions is a name waiting to be merged.

    Tombstone, in the same spirit as `TestQueryBuildingMovedOut`: a second
    definition would drift, and the drift that matters is someone adding "PAY"
    to one copy. The two copies would then disagree about whether a salary
    costs a credit, and the test that guards it would be guarding half of it.
    """

    def test_the_provider_module_does_not_define_its_own_copy(self):
        import app.services.lm_client as lm_client

        assert not hasattr(lm_client, "CHECKABLE_ATTRIBUTES")

    def test_the_constant_names_exactly_the_checkable_attributes(self):
        from app.services.search import CHECKABLE_ATTRIBUTES

        assert set(CHECKABLE_ATTRIBUTES) == {"LOCATION", "CONTACT_METHOD", "MEETING_SPOT"}
        # Reported but never queried. Asserted explicitly because the exclusion
        # is the rule, not the tuple: PAY is a salary figure and ROLE is a job
        # title, and neither is corroborated or refuted by a web search.
        assert "PAY" not in CHECKABLE_ATTRIBUTES
        assert "ROLE" not in CHECKABLE_ATTRIBUTES
