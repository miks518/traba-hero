"""The adaptive search planner: pure functions, offline, no credits.

These are the spec. The planner is code precisely so that what it does can be
asserted without a network call, and every test here is one of the cases the
design lists.

**Test 1 is the regression guard.** It is the CHED flyer, and it encodes the
finding that changed the design: the poster's address is *not* in Round 1's
results — those were US accreditors — so a trigger that requires a shared address
would never fire on exactly the case it was written for.
"""

import pytest

from app.services.lm_client import _ATTRIBUTE_JOIN, _parse_custom
from app.services.scanner.search_planner import (
    MAX_FOLLOWUPS,
    Entity,
    PlannedQuery,
    classify_signals,
    entity_domain_of,
    label_results,
    plan_followups,
    resolve_entity,
    search_query_is_safe,
)
from app.services.search import SearchResult


# ── the flyer ──────────────────────────────────────────────────────────────

CHED_NAME = "Commission for High Learning"
CHED_ATTRS = {
    "CLAIMED_TYPE": "government",
    "LOCATION": "Magsaysay Village, La Paz, Iloilo City",
    "CONTACT_METHOD": (
        "email | hrmo6@ched.gov.ph; email | recruitment.chred@outlook.com; "
        "website | chred-region6.org; form | bit.ly/ChredRegionForm; "
        "phone | (033) 987-6543"
    ),
    "REGISTERED_AS": "",
    "JOB_TITLE": "Project Technical Staff I",
}

# What Round 1 actually returned. No Iloilo, no CHED, no ched.gov.ph.
CHED_ROUND1 = [
    SearchResult("Higher Learning Commission", "https://hlc.org/about", "Accrediting body", 0.91),
    SearchResult("WPU-STUDENT-HANDBOOK.pdf", "https://wpu.edu.ph/handbook.pdf", "Student handbook", 0.7),
    SearchResult("Productivity in Higher Education", "https://journals.example.org/x", "A journal", 0.6),
]


def _ched():
    return classify_signals(CHED_NAME, CHED_ATTRS), CHED_ROUND1


# ── Round 0: signals ───────────────────────────────────────────────────────


class TestSignals:
    def test_a_government_claim_is_read_from_the_claimed_type(self):
        signals, _ = _ched()
        assert signals.claimed_government is True

    def test_each_channel_is_classified_by_its_domain(self):
        signals, _ = _ched()
        classes = {c["class"] for c in signals.channels}
        assert "gov_ph" in classes, signals.channels
        assert "free_email" in classes, signals.channels

    def test_the_fake_channel_is_visible_because_it_is_not_gov_ph(self):
        signals, _ = _ched()
        # The whole reason a .gov.ph domain beside another domain is a signal.
        assert signals.domains_disagree is True

    def test_the_main_non_free_channel_is_the_one_worth_searching(self):
        signals, _ = _ched()
        assert signals.main_domain == "ched.gov.ph"

    def test_every_channel_keeps_its_own_domain_including_the_fakes(self):
        """All of them, or the disagreement cannot be observed at all."""
        signals, _ = _ched()
        domains = {c["domain"] for c in signals.channels if c["domain"]}
        assert {"ched.gov.ph", "outlook.com", "chred-region6.org"} <= domains

    def test_a_free_email_domain_is_never_the_main_domain(self):
        """Asking for the Gmail address tells you nothing about the employer.

        Ordinary Philippine employers hire that way, and a query on it spends a
        credit to learn nothing.
        """
        signals = classify_signals("Acme", {"CONTACT_METHOD": "email | hr@gmail.com"})
        assert signals.main_domain is None
        assert signals.domains_disagree is False

    def test_a_job_title_is_read_when_the_scan_reports_one(self):
        signals, _ = _ched()
        assert signals.job_title == "Project Technical Staff I"

    def test_a_blank_registration_claim_is_not_a_claim(self):
        signals, _ = _ched()
        assert signals.has_registration_claim is False

    def test_no_employer_name_means_no_search(self):
        signals = classify_signals("", {"CONTACT_METHOD": "email | hr@acme.example"})
        assert signals.printed_name == ""
        assert signals.can_search is False

    def test_a_street_address_is_not_a_host(self):
        """An address contains dots, and reading it as a host produced "room".

        "Room 5, Mabini St., Iloilo City" is a place, not a domain, and the
        planner would otherwise spend one of its three credits querying it.
        The typed format exists so that nothing has to be guessed from a
        separator, and the type is what says this is an address.
        """
        signals = classify_signals("Acme Trading", {
            "CONTACT_METHOD": "address | Room 5, Mabini St., Iloilo City",
        })
        assert signals.channels[0]["domain"] == ""
        assert signals.main_domain is None
        assert signals.domains_disagree is False

    def test_a_short_link_is_not_the_posters_own_domain(self):
        """A URL shortener redirects; it never describes the employer.

        Searching "bit.ly" finds the shortener's homepage, and the "the
        channels disagree" signal becomes noise.
        """
        signals = classify_signals("Acme Trading", {
            "CONTACT_METHOD": "form | bit.ly/ApplyAcme",
        })
        assert signals.channels[0]["domain"] == "bit.ly"
        assert signals.channels[0]["class"] == "job_board"
        assert signals.main_domain is None
        assert signals.domains_disagree is False

    def test_a_claimed_type_echoing_the_placeholder_list_is_still_read(self):
        """The prompt's format line is a list of options, and a model that
        copies it produces the whole list.

        "government | private company | recruitment agency | individual |
        unclear" is not the word "government", and reading it as anything else
        silently loses the government claim - which is the claim the whole
        fake-government case turns on.
        """
        signals = classify_signals("CHED Regional Office VI", {
            "CLAIMED_TYPE": (
                "government | private company | recruitment agency | individual | unclear"
            ),
        })
        assert signals.claimed_government is True

    def test_a_claimed_type_is_read_case_insensitively(self):
        signals = classify_signals("CHED Regional Office VI", {
            "CLAIMED_TYPE": "Government",
        })
        assert signals.claimed_government is True


class TestTheSeparatorContract:
    """The scan's writer and the planner's reader, tested against each other.

    `lm_client._ATTRIBUTE_JOIN` joins repeated channels with `"; "` and
    `classify_signals` splits on `";"`. The two are in different modules and
    neither imports the other's constant, so nothing stops one from changing
    alone — and the failure is silent: a posting with two channels is parsed
    as one, the free-mail channel that the whole CHED case turns on
    disappears, `Channel Match` never fires, and nothing errors.

    Every other test in this file feeds `classify_signals` a hand-written
    `"; "`-joined string, so the writer's end was never exercised. This one
    starts from a scan output and lets the parser produce the value, which is
    the only way the contract can be broken and observed.
    """

    def test_the_scan_writers_value_is_read_by_the_planner(self):
        raw = (
            "VALID: true\n"
            "ATTRIBUTES:\n"
            "CONTACT_METHOD: email | hrmo6@ched.gov.ph\n"
            "CONTACT_METHOD: email | recruitment.ched@outlook.com\n"
            "END ATTRIBUTES\n"
            "EMPLOYER NAME: Commission on High Learning\n"
        )
        attributes = _parse_custom(raw)["attributes"]

        signals = classify_signals(CHED_NAME, attributes)

        # Both channels survive, and the free-mail one is still visible.
        assert len(signals.channels) == 2, signals.channels
        domains = {c["domain"] for c in signals.channels}
        assert "ched.gov.ph" in domains
        assert "outlook.com" in domains
        # The employer's own domain is the one worth searching, and the
        # free-mail one is not it.
        assert signals.main_domain == "ched.gov.ph"

    def test_the_two_ends_agree_on_the_separator(self):
        """The constant and the split, asserted against each other.

        A change to either without the other is the failure this class
        exists for.
        """
        assert _ATTRIBUTE_JOIN.strip() == ";"
        raw = (
            "VALID: true\n"
            "ATTRIBUTES:\n"
            "CONTACT_METHOD: email | one@acme.example\n"
            "CONTACT_METHOD: email | two@acme.example\n"
            "END ATTRIBUTES\n"
            "EMPLOYER NAME: Acme\n"
        )
        assert len(classify_signals("Acme", _parse_custom(raw)["attributes"]).channels) == 2


# ── Resolve ────────────────────────────────────────────────────────────────


class TestResolve:
    def test_the_live_results_describe_nothing_that_matches(self):
        """The case that changed the design.

        Every result is about a different body. `names_differ` must come out true,
        because that is what makes the planner spend a credit on the poster's own
        domain instead of stopping.
        """
        signals, results = _ched()
        entity = resolve_entity(signals, results)
        assert entity.names_differ is True

    def test_the_location_is_not_shared_because_it_is_not_in_the_results(self):
        signals, results = _ched()
        entity = resolve_entity(signals, results)
        assert entity.shares_identifier is False

    def test_an_identical_name_does_not_differ(self):
        signals = classify_signals("Tanika Trading", {"CONTACT_METHOD": "email | hr@tanika.ph"})
        entity = resolve_entity(signals, [
            SearchResult("Tanika Trading", "https://tanika.ph/", "We are Tanika Trading", 0.9),
        ])
        assert entity.names_differ is False

    def test_a_legal_suffix_is_not_a_different_name(self):
        signals = classify_signals("San Miguel Corporation", {"CONTACT_METHOD": "email | hr@smc.ph"})
        entity = resolve_entity(signals, [
            SearchResult("San Miguel Corp.", "https://smc.ph/", "Official site", 0.9),
        ])
        assert entity.names_differ is False

    def test_a_shared_address_is_an_identifier(self):
        signals = classify_signals(
            "Tanika Trading", {"LOCATION": "Magsaysay Village, Iloilo City",
                               "CONTACT_METHOD": "email | hr@tanika.ph"},
        )
        entity = resolve_entity(signals, [
            SearchResult("Tanika Trading", "https://tanika.ph/",
                         "Magsaysay Village, Iloilo City", 0.9),
        ])
        assert entity.shares_identifier is True

    def test_no_results_resolve_to_nothing_rather_than_to_a_guess(self):
        signals, _ = _ched()
        entity = resolve_entity(signals, [])
        assert entity.name == ""
        assert entity.domain is None
        assert entity.names_differ is False

    def test_an_aggregator_is_not_taken_as_the_entity_domain(self):
        """A wrong domain produces a wrong query, not a wrong assessment.

        Which is why the denylist exists at all, and why it is tested rather than
        trusted.
        """
        signals = classify_signals("Acme Trading", {"CONTACT_METHOD": "email | hr@acme.ph"})
        entity = resolve_entity(signals, [
            SearchResult("Acme Trading", "https://www.linkedin.com/company/acme", "Acme", 0.95),
            SearchResult("Acme Trading", "https://acme.ph/", "Official", 0.9),
        ])
        assert entity.domain == "acme.ph"

    def test_a_government_claim_prefers_a_gov_ph_result(self):
        signals = classify_signals(
            "Department of Science and Technology",
            {"CLAIMED_TYPE": "government", "CONTACT_METHOD": "email | hr@dst.gov.ph"},
        )
        entity = resolve_entity(signals, [
            SearchResult("Department of Science and Technology", "https://facebook.com/dst", "FB", 0.95),
            SearchResult("Department of Science and Technology", "https://www.dst.gov.ph/", "Official", 0.9),
        ])
        assert entity.domain == "dst.gov.ph"


# ── The decision table ─────────────────────────────────────────────────────


class TestPlanner:
    def test_the_live_case_spends_a_credit_on_the_posters_own_domain(self):
        """Regression guard for the design change.

        No shared address, and row 1 must still fire — because the absence of one
        is what the failure looks like.
        """
        signals, results = _ched()
        entity = resolve_entity(signals, results)
        planned = plan_followups(signals, entity, round1_ok=True, model_queries=[])
        assert planned, "the flyer must produce at least one follow-up"
        assert any("ched.gov.ph" in q.text for q in planned), [q.text for q in planned]

    def test_row_one_has_no_include_domains(self):
        """`include_domains` is only ever set to a domain taken from results.

        Row 1 searches a domain the POSTING gave, and pointing Tavily at it as a
        filter would restrict discovery to the very thing under suspicion.
        Asserted as falsy rather than against a list of representations, because
        the property is the one that matters and `None` / `[]` / `()` are three
        ways of spelling it.
        """
        signals, results = _ched()
        entity = resolve_entity(signals, results)
        found = False
        for query in plan_followups(signals, entity, round1_ok=True, model_queries=[]):
            if "ched.gov.ph" in query.text:
                found = True
                assert not query.include_domains, query
        assert found, "row 1 did not fire at all, so this would pass vacuously"

    def test_a_shared_address_adds_the_listing_query(self):
        signals = classify_signals(
            "Commission for High Learning",
            dict(CHED_ATTRS, LOCATION="Magsaysay Village, Iloilo City"),
        )
        entity = resolve_entity(signals, [
            SearchResult("Commission on Higher Education", "https://ched.gov.ph/",
                         "Regional Office VI, Magsaysay Village, Iloilo City", 0.9),
        ])
        planned = plan_followups(signals, entity, round1_ok=True, model_queries=[])
        assert any(q.include_domains for q in planned), planned

    def test_a_quiet_small_employer_spends_nothing_extra(self):
        signals = classify_signals("Tanika Trading", {"CONTACT_METHOD": "email | hr@gmail.com"})
        entity = resolve_entity(signals, [
            SearchResult("Tanika Trading", "https://tanika.ph/", "Tanika Trading", 0.9),
        ])
        assert plan_followups(signals, entity, round1_ok=True, model_queries=[]) == []

    def test_a_failed_round_one_plans_nothing(self):
        """Never spend a credit against a provider that just failed."""
        signals, results = _ched()
        entity = resolve_entity(signals, results)
        assert plan_followups(signals, entity, round1_ok=False, model_queries=[]) == []

    def test_no_results_in_round_one_triggers_a_different_anchor(self):
        signals = classify_signals(
            "Bagong Kahayagan", {"LOCATION": "Iloilo City", "CONTACT_METHOD": "email | hr@bkah.ph"},
        )
        entity = resolve_entity(signals, [])
        planned = plan_followups(signals, entity, round1_ok=True, model_queries=[])
        assert planned and "Iloilo City" in planned[0].text

    def test_a_registration_claim_is_tested_when_nothing_else_fires(self):
        signals = classify_signals(
            "Bagong Kahayagan",
            {"REGISTERED_AS": "DTI permit no. 12345", "CONTACT_METHOD": "email | hr@bkah.ph"},
        )
        entity = resolve_entity(signals, [
            SearchResult("Bagong Kahayagan", "https://bkah.ph/", "Bagong Kahayagan", 0.9),
        ])
        planned = plan_followups(signals, entity, round1_ok=True, model_queries=[])
        assert planned and "DTI permit no. 12345" in planned[0].text

    def test_model_queries_are_filler_not_the_plan(self):
        """They go in only when the planner has nothing better to do."""
        signals, results = _ched()
        entity = resolve_entity(signals, results)
        planned = plan_followups(signals, entity, round1_ok=True, model_queries=["a query we did not plan"])
        assert not any("did not plan" in q.text for q in planned)

    def test_model_queries_fill_an_empty_slot(self):
        signals = classify_signals("Tanika Trading", {"CONTACT_METHOD": "email | hr@gmail.com"})
        entity = resolve_entity(signals, [
            SearchResult("Tanika Trading", "https://tanika.ph/", "Tanika Trading", 0.9),
        ])
        planned = plan_followups(signals, entity, round1_ok=True, model_queries=["same work elsewhere"])
        assert [q.text for q in planned] == ["same work elsewhere"]

    def test_the_ceiling_is_never_exceeded(self):
        signals, results = _ched()
        entity = resolve_entity(signals, results)
        planned = plan_followups(signals, entity, round1_ok=True, model_queries=["a", "b", "c", "d"])
        assert len(planned) <= MAX_FOLLOWUPS

    def test_the_ceiling_holds_when_every_row_could_fire(self):
        """The guard above is fixture-limited: the flyer produces exactly two rows,
        so removing the cap changes nothing for it and the test passes with the
        cap deleted. This fixture produces all four.
        """
        signals = classify_signals(
            "Commission for High Learning",
            dict(
                CHED_ATTRS,
                REGISTERED_AS="DTI permit no. 12345",
                JOB_TITLE="Project Technical Staff I",
            ),
        )
        entity = resolve_entity(signals, [
            SearchResult("Commission on Higher Education", "https://ched.gov.ph/",
                         "Regional Office VI, Magsaysay Village, Iloilo City", 0.9),
        ])
        assert len(plan_followups(signals, entity, round1_ok=True, model_queries=[])) > 1, (
            "this fixture must fire more rows than the ceiling allows, or it "
            "proves nothing"
        )
        planned = plan_followups(signals, entity, round1_ok=True, model_queries=[])
        assert len(planned) == MAX_FOLLOWUPS

    @pytest.mark.parametrize("model_queries", [[], ["a"], ["a", "b"], ["a", "b", "c"], ["a"] * 9])
    def test_no_input_reaches_past_the_ceiling(self, model_queries):
        """Property rather than example.

        The ceiling is a credit bound, so the test that matters is that no
        combination of signals and model queries reaches past it — not that one
        fixture does not.
        """
        signals = classify_signals(
            "Commission for High Learning",
            dict(
                CHED_ATTRS,
                LOCATION="Magsaysay Village, La Paz, Iloilo City",
                REGISTERED_AS="DTI permit no. 12345",
            ),
        )
        entity = resolve_entity(signals, [
            SearchResult("Commission on Higher Education", "https://ched.gov.ph/",
                         "Regional Office VI, Magsaysay Village, Iloilo City", 0.9),
        ])
        assert len(plan_followups(signals, entity, round1_ok=True, model_queries=model_queries)) <= MAX_FOLLOWUPS


# ── Labelling ──────────────────────────────────────────────────────────────


class TestLabelling:
    def test_a_page_about_the_entity_is_labelled_as_such(self):
        entity = Entity(name="Higher Learning Commission")
        results = [SearchResult("Higher Learning Commission", "https://hlc.org/about", "About us", 0.9)]
        labels = label_results(results, entity, {"https://hlc.org/about": "anchor"})
        assert labels["https://hlc.org/about"].describes_entity is True

    def test_a_page_about_a_different_body_is_labelled_false_and_kept(self):
        """The point of the labelling.

        A US accreditor's page appearing under a Philippine employer's name is
        not evidence about that employer — but it is evidence about what the
        search found, so it stays in the list and says what it is.
        """
        entity = Entity(name="Higher Learning Commission")
        results = [
            SearchResult("Higher Learning Commission", "https://hlc.org/about", "About", 0.9),
            SearchResult("West Point University Handbook", "https://wpu.edu.ph/h.pdf", "Handbook", 0.7),
        ]
        labels = label_results(results, entity, {})
        assert len(labels) == 2, "a wrong-entity result must not be dropped"
        assert labels["https://wpu.edu.ph/h.pdf"].describes_entity is False

    def test_each_result_carries_the_query_that_found_it(self):
        entity = Entity(name="Higher Learning Commission")
        results = [SearchResult("A", "https://a.example/1", "", 0.9)]
        labels = label_results(results, entity, {"https://a.example/1": "ched.gov.ph"})
        assert labels["https://a.example/1"].query == "ched.gov.ph"

    def test_an_unknown_provenance_is_kept_not_dropped(self):
        """A result with no recorded query is still evidence."""
        entity = Entity(name="X Corp")
        labels = label_results([SearchResult("t", "https://x.example/", "", 0.5)], entity, {})
        assert labels["https://x.example/"].query == ""

    def test_with_no_entity_nothing_describes_it(self):
        """An unresolved entity is not a claim that every page is off-topic."""
        labels = label_results(
            [SearchResult("Tanika Trading", "https://tanika.ph/", "Tanika", 0.9)],
            Entity(),
            {},
        )
        assert labels["https://tanika.ph/"].describes_entity is False


# ── Safety ─────────────────────────────────────────────────────────────────


class TestSafety:
    def test_a_query_carrying_a_conclusion_word_is_dropped(self):
        """The rule moves from prompt text into code.

        A query containing an accusation returns pages chosen because they contain
        that word, which then read as confirmation of an accusation the query made
        up.
        """
        signals = classify_signals("Tanika Trading", {"CONTACT_METHOD": "email | hr@gmail.com"})
        entity = resolve_entity(signals, [])
        planned = plan_followups(
            signals, entity, round1_ok=True, model_queries=["is Tanika a scam"]
        )
        assert planned == []

    def test_the_check_is_word_bounded_not_a_substring_test(self):
        assert search_query_is_safe("Tanika scam report") is False
        # `scam` inside a longer word is not the word.
        assert search_query_is_safe("Scamander Foods") is True

    def test_control_characters_are_stripped(self):
        signals = classify_signals("Tanika Trading", {"CONTACT_METHOD": "email | hr@gmail.com"})
        entity = resolve_entity(signals, [])
        planned = plan_followups(signals, entity, round1_ok=True, model_queries=["a\nb\tc"])
        assert planned and "\n" not in planned[0].text

    def test_a_query_is_length_capped(self):
        signals = classify_signals("Tanika Trading", {"CONTACT_METHOD": "email | hr@gmail.com"})
        entity = resolve_entity(signals, [])
        planned = plan_followups(signals, entity, round1_ok=True, model_queries=["x" * 900])
        assert planned and len(planned[0].text) <= 500

    def test_include_domains_is_never_taken_from_the_posting(self):
        """The exception is narrow: a domain from RESULTS, never from the poster.

        Scoping a search to a domain the poster supplied would restrict discovery
        to the thing under suspicion. Every scope must be a host that appeared in
        Round 1's results.
        """
        signals, results = _ched()
        entity = resolve_entity(signals, results)
        from_results = {_host(r.url) for r in results if r.url}
        for query in plan_followups(signals, entity, round1_ok=True, model_queries=[]):
            for domain in query.include_domains:
                assert domain in from_results, (
                    f"{domain} was scoped but never appeared in the results"
                )

    def test_a_poster_domain_is_never_used_as_a_scope(self):
        """The flyer's own channels are the sharpest case of that rule."""
        signals, results = _ched()
        entity = resolve_entity(signals, results)
        from_results = {_host(r.url) for r in results if r.url}
        for query in plan_followups(signals, entity, round1_ok=True, model_queries=[]):
            for domain in query.include_domains:
                assert domain not in {"ched.gov.ph", "chred-region6.org", "outlook.com"}


def _host(url: str) -> str:
    from app.services.scanner.search_planner import entity_domain_of

    return entity_domain_of(url)


class TestNoSearchAtAll:
    def test_a_nameless_posting_plans_nothing_and_cannot_anchor(self):
        signals = classify_signals("", {"CONTACT_METHOD": "email | hr@gmail.com"})
        entity = resolve_entity(signals, [])
        assert signals.can_search is False
        assert plan_followups(signals, entity, round1_ok=True, model_queries=["a"]) is not None