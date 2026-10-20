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
    severity: str = "high",
    code: str = "",
) -> Anomaly:
    return Anomaly(flag=flag, reasoning="r", severity=severity, code=code)


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

        assert result.status == "yellow"
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

        assert result.status == "yellow"
        assert result.escalation == "free_email"

    def test_a_free_email_with_no_official_channel_is_still_yellow(self):
        result = assess_channel_match(
            ChannelFacts(printed_channels=("someone@gmail.com",))
        )

        assert result.status == "yellow"
        assert result.escalation == "free_email"


class TestGovernmentClaims:
    def test_a_government_claim_with_a_free_email_is_red(self):
        result = assess_channel_match(FAKE_CHED)

        assert result.status == "red"
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

        assert result.status == "red"
        assert result.escalation == "government"

    def test_a_government_mention_that_is_not_a_claim_is_not_enough(self):
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("info@example.com",),
                official_channels=("example.com",),
                government_claim=False,
            )
        )

        assert (result.status, result.escalation) == ("green", "match")

    def test_an_official_gov_ph_domain_makes_it_government_even_without_the_flag(self):
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("info@example.com",),
                official_channels=("ched.gov.ph",),
                government_claim=False,
            )
        )

        assert result.status == "red"
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

        assert result.status == "red"
        assert result.escalation == "government"
        assert result.strong is True

    def test_the_chred_domain_is_a_lookalike_of_ched(self):
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("chred-region6.org",),
                official_channels=("ched.org.ph",),
            )
        )

        assert result.status == "red"
        assert result.escalation == "lookalike"
        assert result.strong is True

    def test_a_typo_of_the_official_domain_is_a_lookalike(self):
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("knollrigdes.com.ph",),
                official_channels=("knollridges.com.ph",),
            )
        )

        assert result.status == "red"
        assert result.escalation == "lookalike"

    def test_a_brand_with_a_suffix_is_a_lookalike(self):
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("knollridgescareers.com",),
                official_channels=("knollridges.com.ph",),
            )
        )

        assert result.status == "red"
        assert result.escalation == "lookalike"

    def test_a_different_business_is_not_a_lookalike(self):
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("notacme.com",),
                official_channels=("acme.com.ph",),
            )
        )

        assert result.status == "yellow"
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

        assert result.status == "red"
        assert result.escalation == "lookalike"

    def test_the_official_domain_itself_is_a_match_not_a_lookalike(self):
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("https://www.knollridges.com.ph/contact",),
                official_channels=("knollridges.com.ph",),
            )
        )

        assert (result.status, result.escalation) == ("green", "match")


class TestTheCombinationRule:
    def test_free_email_plus_a_high_finding_is_red(self):
        result = assess_channel_match(
            KNOLLRIDGES, independent_findings=("Asks for a fee",)
        )

        assert result.status == "red"
        assert result.escalation == "free_email_with_findings"
        assert result.strong is False
        assert "separate finding" in result.explanation

    def test_a_different_channel_plus_a_high_finding_is_red(self):
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("recruiter.example/apply",),
                official_channels=("knollridges.com.ph",),
            ),
            independent_findings=("Invites applicants to a chat-only interview",),
        )

        assert result.status == "red"
        assert result.escalation == "unconfirmed_with_findings"

    def test_a_different_channel_alone_is_yellow(self):
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("recruiter.example/apply",),
                official_channels=("knollridges.com.ph",),
            )
        )

        assert result.status == "yellow"
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
            ),
            independent_findings=("Asks for a fee",),
        )

        assert result.status == "yellow"
        assert result.escalation == "no_data"

    def test_a_matching_channel_is_green(self):
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("info@knollridges.com.ph",),
                official_channels=("https://knollridges.com.ph",),
            )
        )

        assert (result.status, result.escalation) == ("green", "match")

    def test_a_matching_phone_is_green(self):
        result = assess_channel_match(
            ChannelFacts(
                printed_channels=("+63 2 8123 4567",),
                official_channels=("+63 2 8123 4567",),
            )
        )

        assert (result.status, result.escalation) == ("green", "match")


class TestTheCardRules:
    def test_an_old_model_channel_match_is_demoted_to_yellow_no_data(self):
        """A stored response with no `escalation` came from before the facts
        split. Its status is the model's, and the model's status is the thing this
        split stopped trusting.
        """
        item = VerificationItem(
            label="Channel Match",
            status="red",
            explanation="A different domain is a contradiction.",
            source_title="Old result",
            source_url="https://example.com/old",
        )

        applied = apply_channel_rules([item], [], {"Channel Match"})

        assert applied[0].status == "yellow"
        assert applied[0].escalation == "no_data"
        assert applied[0].source_url == ""

    def test_the_category_is_removed_when_the_posting_made_no_channel_claim(self):
        item = VerificationItem(
            label="Channel Match",
            status="yellow",
            explanation="x",
            escalation="free_email",
        )
        other = VerificationItem(
            label="Company Existence",
            status="yellow",
            explanation="y",
        )

        applied = apply_channel_rules([other, item], [], {"Company Existence"})

        assert [i.label for i in applied] == ["Company Existence"]

    def test_a_yellow_free_email_is_upgraded_by_a_fee_in_the_request(self):
        item = VerificationItem(
            label="Channel Match",
            status="yellow",
            explanation="A free email is ordinary.",
            escalation="free_email",
        )

        applied = apply_channel_rules(
            [item], [_anomaly(code="FEE_MANDATORY", severity="high")], {"Channel Match"}
        )

        assert applied[0].status == "red"
        assert applied[0].escalation == "free_email_with_findings"
        assert "Asks for a fee" in applied[0].explanation

    def test_a_low_generic_finding_does_not_upgrade_a_free_email(self):
        item = VerificationItem(
            label="Channel Match",
            status="yellow",
            explanation="A free email is ordinary.",
            escalation="free_email",
        )

        applied = apply_channel_rules(
            [item], [_anomaly(severity="low", code="OTHER")], {"Channel Match"}
        )

        assert applied[0].status == "yellow"

    def test_an_escalating_code_upgrades_even_at_low_severity(self):
        """The code names a concrete loss; the model's severity is not the only
        gate. A low-severity `FEE_MANDATORY` is still a fee.
        """
        item = VerificationItem(
            label="Channel Match",
            status="yellow",
            explanation="A free email is ordinary.",
            escalation="free_email",
        )

        applied = apply_channel_rules(
            [item], [_anomaly(severity="low", code="FEE_MANDATORY")], {"Channel Match"}
        )

        assert applied[0].status == "red"

    def test_a_missing_card_is_added_only_when_there_is_another_usable_check(self):
        other = VerificationItem(
            label="Company Existence",
            status="yellow",
            explanation="y",
        )

        applied = apply_channel_rules([other], [], {"Channel Match", "Company Existence"})

        assert [i.label for i in applied] == ["Company Existence", "Channel Match"]
        assert applied[1].escalation == "no_data"

    def test_a_missing_card_is_not_added_to_an_empty_response(self):
        """The empty response must reach the flow's failsafe, not look like a
        usable yellow check.
        """
        assert apply_channel_rules([], [], {"Channel Match"}) == []


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
