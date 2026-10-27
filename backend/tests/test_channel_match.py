"""Channel Match is a code decision over model-reported facts.

The regressions this file exists for are both real:

* Knollridges: a real employer whose posting used
  `yvonne.knollridges@gmail.com` while its own site was `knollridges.com.ph`.
  The old prompt called any different channel red, and the model's own
  `risk_level` turned that into "Do not proceed". The corrected outcome is a
  yellow informational card and a level that still has to come from the posting.
* Fake CHED: a poster using the real CHED Regional Office VI seal and
  `ched.gov.ph`, but sending applicants to `recruitment.chred@outlook.com`,
  `chred-region6.org`, and `info@chred-region6.org`, with a mandatory P1,500 fee.
  That is a government claim with non-.gov.ph channels, and it stays red.

The rules are narrow on purpose. Free email alone is not a contradiction; a
different channel alone is yellow; red needs a government claim, a lookalike, or
a non-matching channel plus an independent finding.
"""

from app.models.schemas import Anomaly, VerificationItem
from app.services.scanner.channel_match import (
    ChannelFacts,
    apply_channel_rules,
    assess_channel_match,
    has_channel_content,
    read_channel_facts,
    with_official_only_if_retrieved,
)


KNOLLRIDGES = ChannelFacts(
    printed_channels=("yvonne.knollridges@gmail.com",),
    official_channels=("knollridges.com.ph",),
    finding=(
        "The posting gives yvonne.knollridges@gmail.com and the company site is "
        "knollridges.com.ph."
    ),
    source_title="Knollridges",
    source_url="https://knollridges.com.ph",
)

FAKE_CHED = ChannelFacts(
    printed_channels=(
        "recruitment.chred@outlook.com",
        "chred-region6.org",
        "info@chred-region6.org",
        "hrmo6@ched.gov.ph",
    ),
    official_channels=("ched.gov.ph",),
    government_claim=True,
    finding=(
        "The posting gives recruitment.chred@outlook.com and the agency site is "
        "ched.gov.ph."
    ),
    source_title="CHED Regional Office VI",
    source_url="https://ched.gov.ph",
)


def _anomaly(
    flag: str = "Asks for a fee",
    code: str = "",
) -> Anomaly:
    return Anomaly(flag=flag, reasoning="r", code=code)


class TestTheFactsAreReadTolerantly:
    def test_a_missing_object_is_no_facts(self):
        assert read_channel_facts(None) is None
        assert read_channel_facts("not an object") is None

    def test_an_empty_object_is_an_empty_facts_record_not_none(self):
        facts = read_channel_facts({})

        assert facts is not None
        assert facts.printed_channels == ()
        assert facts.official_channels == ()
        assert facts.government_claim is False

    def test_a_single_string_is_accepted_as_one_channel(self):
        facts = read_channel_facts({"printed_channels": "info@example.com"})

        assert facts.printed_channels == ("info@example.com",)

    def test_a_string_boolean_is_read(self):
        assert read_channel_facts({"government_claim": "true"}).government_claim is True
        assert read_channel_facts({"government_claim": "false"}).government_claim is False

    def test_blank_entries_are_dropped(self):
        facts = read_channel_facts(
            {"printed_channels": ["info@example.com", "", "   ", None]}
        )

        assert facts.printed_channels == ("info@example.com",)

    def test_only_a_finding_is_not_enough_to_compare(self):
        facts = read_channel_facts({"finding": "The posting gives an email."})

        assert has_channel_content(facts) is False


class TestFreeEmailIsInformational:
    def test_the_knollridges_case_is_yellow_not_red(self):
        result = assess_channel_match(KNOLLRIDGES)

        assert result.status == "unknown"
        assert result.escalation == "free_email"
        assert result.strong is False
        assert "ordinary in Philippine job postings" in result.explanation
        assert "not a contradiction by itself" in result.explanation

    def test_the_company_name_in_the_local_part_is_not_treated_as_a_domain_match(self):
        """`@gmail.com` is the domain. The local part naming the company is why a
        free address is usable, not why it is suspicious.
        """
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("knollridges@gmail.com",),
                official_channels=("knollridges.com.ph",),
            )
        )

        assert result.status == "unknown"
        assert result.escalation == "free_email"

    def test_a_free_email_with_no_official_channel_is_still_yellow(self):
        result = assess_channel_match(
            ChannelFacts(printed_channels=("someone@gmail.com",))
        )

        assert result.status == "unknown"
        assert result.escalation == "free_email"


class TestGovernmentClaims:
    def test_a_government_claim_with_a_free_email_is_red(self):
        result = assess_channel_match(FAKE_CHED)

        assert result.status == "contradicted"
        assert result.escalation == "government"
        assert result.strong is True
        assert "government office" in result.explanation
        assert "ched.gov.ph" in result.explanation

    def test_a_government_claim_with_no_official_channel_is_still_red_until_binding(self):
        """The posting itself made both claims: it is a government office and the
        contact is not on a government domain. The source binding that follows can
        still demote it if no result backs the official side.
        """
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("recruitment@example.com",),
                government_claim=True,
            )
        )

        assert result.status == "contradicted"
        assert result.escalation == "government"

    def test_a_government_mention_that_is_not_a_claim_is_not_enough(self):
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("info@example.com",),
                official_channels=("example.com",),
                government_claim=False,
            )
        )

        assert (result.status, result.escalation) == ("confirmed", "match")

    def test_an_official_gov_ph_domain_makes_it_government_even_without_the_flag(self):
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("info@example.com",),
                official_channels=("ched.gov.ph",),
                government_claim=False,
            )
        )

        assert result.status == "contradicted"
        assert result.escalation == "government"


class TestLookalikes:
    def test_the_chred_domain_against_a_gov_ph_official_is_a_government_contradiction(self):
        """The government rule is checked first because a `.gov.ph` official
        domain makes the non-.gov.ph channel a contradiction on its own. The
        lookalike is the second reason, not the one that fires.
        """
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("chred-region6.org",),
                official_channels=("ched.gov.ph",),
            )
        )

        assert result.status == "contradicted"
        assert result.escalation == "government"
        assert result.strong is True

    def test_the_chred_domain_is_a_lookalike_of_ched(self):
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("chred-region6.org",),
                official_channels=("ched.org.ph",),
            )
        )

        assert result.status == "contradicted"
        assert result.escalation == "lookalike"
        assert result.strong is True

    def test_a_typo_of_the_official_domain_is_a_lookalike(self):
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("knollrigdes.com.ph",),
                official_channels=("knollridges.com.ph",),
            )
        )

        assert result.status == "contradicted"
        assert result.escalation == "lookalike"

    def test_a_brand_with_a_suffix_is_a_lookalike(self):
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("knollridgescareers.com",),
                official_channels=("knollridges.com.ph",),
            )
        )

        assert result.status == "contradicted"
        assert result.escalation == "lookalike"

    def test_a_different_business_is_not_a_lookalike(self):
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("notacme.com",),
                official_channels=("acme.com.ph",),
            )
        )

        assert result.status == "unknown"
        assert result.escalation == "unconfirmed"

    def test_the_paf_portal_is_a_lookalike_of_the_official_mil_ph_site(self):
        """The 2026-10-16 live case, now caught by code rather than by asking
        the model to treat every different channel as red.

        `paf.mil.ph` is the official site; `paf-recruitment-portal.ph` uses the
        same `paf` brand. The `mil.ph` suffix has to be in the label list or the
        brand would be read as `mil` and the lookalike would be missed.
        """
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("paf-recruitment-portal.ph",),
                official_channels=("paf.mil.ph",),
            )
        )

        assert result.status == "contradicted"
        assert result.escalation == "lookalike"

    def test_the_official_domain_itself_is_a_match_not_a_lookalike(self):
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("https://www.knollridges.com.ph/contact",),
                official_channels=("knollridges.com.ph",),
            )
        )

        assert (result.status, result.escalation) == ("confirmed", "match")


class TestTheCombinationRule:
    def test_the_parser_does_not_combine_at_all(self):
        """`assess_channel_match` used to take the scan's finding labels, and a
        free email plus any high or mid finding became a red card. That is the
        rule the corpus measured: 25 points for the free email, 12 for the
        applicant packet, and two legitimate postings called "Proceed with
        caution" (37 both times).

        The combination now lives in `apply_channel_rules`, which is the stage
        that holds the request class, and it needs a prohibited request to fire.
        Leaving the parameter here would have kept a second route to the same
        red, asserted by tests and used by no caller.
        """
        import inspect

        parameters = inspect.signature(assess_channel_match).parameters
        assert "independent_findings" not in parameters

    def test_a_free_email_at_the_parser_stage_is_always_yellow(self):
        """No findings reach this stage at all now, so the parser has no way to
        escalate. A free email is ordinary in Philippine hiring and the prompt
        says so.
        """
        result = assess_channel_match(KNOLLRIDGES)

        assert (result.status, result.escalation) == ("unknown", "free_email")

    def test_a_different_channel_alone_is_yellow(self):
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("recruiter.example/apply",),
                official_channels=("knollridges.com.ph",),
            )
        )

        assert result.status == "unknown"
        assert result.escalation == "unconfirmed"
        assert "not that channel" in result.explanation

    def test_a_phone_that_does_not_match_is_yellow_not_a_combination(self):
        """A different phone number or meeting place has no domain to imitate.
        Without a domain, the combination rule is not applied; a mall address from
        a real employer is an ordinary fact, not a contradiction.
        """
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("0917 123 4567",),
                official_channels=("+63 2 8123 4567",),
            )
        )

        assert result.status == "unknown"
        assert result.escalation == "no_data"

    def test_a_matching_channel_is_green(self):
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("info@knollridges.com.ph",),
                official_channels=("https://knollridges.com.ph",),
            )
        )

        assert (result.status, result.escalation) == ("confirmed", "match")

    def test_a_matching_phone_is_green(self):
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("+63 2 8123 4567",),
                official_channels=("+63 2 8123 4567",),
            )
        )

        assert (result.status, result.escalation) == ("confirmed", "match")


class TestTheCardRules:
    def test_an_old_model_channel_match_is_demoted_to_yellow_no_data(self):
        """A stored response with no `escalation` came from before the facts
        split. Its status is the model's, and the model's status is the thing this
        split stopped trusting.
        """
        item = VerificationItem(
            label="Channel Match",
            status="contradicted",
            explanation="A different domain is a contradiction.",
            source_title="Old result",
            source_url="https://example.com/old",
        )

        applied = apply_channel_rules([item], "", {"Channel Match"})

        assert applied[0].status == "unknown"
        assert applied[0].escalation == "no_data"
        assert applied[0].source_url == ""

    def test_the_category_is_removed_when_the_posting_made_no_channel_claim(self):
        item = VerificationItem(
            label="Channel Match",
            status="unknown",
            explanation="x",
            escalation="free_email",
        )
        other = VerificationItem(
            label="Company Existence",
            status="unknown",
            explanation="y",
        )

        applied = apply_channel_rules([other, item], "", {"Company Existence"})

        assert [i.label for i in applied] == ["Company Existence"]

    def test_a_free_email_with_an_ordinary_request_stays_yellow(self):
        """A Gmail address is ordinary in Philippine hiring, and the scan prompt
        says so. The corpus measured the cost of the old rule: 25 points for the
        free email plus 12 for the applicant packet put two legitimate postings
        on "Proceed with caution" (37 both times).
        """
        item = VerificationItem(
            label="Channel Match",
            status="unknown",
            explanation="A free email is ordinary.",
            escalation="free_email",
        )

        applied = apply_channel_rules([item], "ordinary", {"Channel Match"})

        assert applied[0].status == "unknown"
        assert applied[0].escalation == "free_email"

    def test_a_free_email_with_a_prohibited_request_becomes_red(self):
        """The combination that means something: a channel the employer does not
        control, plus a request the rules prohibit. Rare by construction, so the
        red it produces is worth looking at.
        """
        item = VerificationItem(
            label="Channel Match",
            status="unknown",
            explanation="A free email is ordinary.",
            escalation="free_email",
        )

        applied = apply_channel_rules([item], "prohibited", {"Channel Match"})

        assert applied[0].status == "contradicted"
        assert applied[0].escalation == "free_email_with_findings"
        assert "prohibit" in applied[0].explanation.lower()

    def test_an_unclassified_request_does_not_upgrade_a_free_email(self):
        """A question is not a charge. A fee with no stated recipient leaves the
        class unclassified, and the card stays a note."""
        item = VerificationItem(
            label="Channel Match",
            status="unknown",
            explanation="A free email is ordinary.",
            escalation="free_email",
        )

        applied = apply_channel_rules([item], "unclassified", {"Channel Match"})

        assert applied[0].status == "unknown"
        assert applied[0].escalation == "free_email"

    def test_a_missing_card_is_added_only_when_there_is_another_usable_check(self):
        other = VerificationItem(
            label="Company Existence",
            status="unknown",
            explanation="y",
        )

        applied = apply_channel_rules([other], "", {"Channel Match", "Company Existence"})

        assert [i.label for i in applied] == ["Company Existence", "Channel Match"]
        assert applied[1].escalation == "no_data"

    def test_a_missing_card_is_not_added_to_an_empty_response(self):
        """The empty response must reach the flow's failsafe, not look like a
        usable yellow check.
        """
        assert apply_channel_rules([], "", {"Channel Match"}) == []


def test_the_independent_finding_reader_is_gone():
    """`_first_independent_finding` escalated on any high or mid finding, which
    is how a free email plus the ordinary applicant packet became a red card
    worth 25 points. The request class is now the only gate, and it is decided
    by `request_class.classify_request` from the facts on the posting.

    `ESCALATING_CODES` existed only to feed that reader, so it goes with it.
    """
    import app.services.scanner.channel_match as channel_match

    assert not hasattr(channel_match, "_first_independent_finding")
    assert not hasattr(channel_match, "ESCALATING_CODES")


class TestOfficialChannelsNeedARetrievedSource:
    def test_an_unretrieved_source_drops_the_official_side(self):
        facts = with_official_only_if_retrieved(KNOLLRIDGES, retrieved=False)

        assert facts.official_channels == ()
        assert facts.source_url == ""
        assert facts.printed_channels == ("yvonne.knollridges@gmail.com",)

    def test_a_retrieved_source_keeps_the_official_side(self):
        facts = with_official_only_if_retrieved(KNOLLRIDGES, retrieved=True)

        assert facts.official_channels == ("knollridges.com.ph",)
        assert facts.source_url == "https://knollridges.com.ph"
