"""A category is reported only when the posting made the claim it tests.

The prompt used to say: "Where the request states nothing for a category, there
is no claim to test - report yellow and say in the finding that the posting
stated nothing to check." That instructed the model to emit all six categories
every time, so a posting naming no location produced a "Location / Branch" card
reading "the posting stated nothing to check".

Three problems in one:

- A card asserting a check that was never made is the same defect as a
  "Evidence Summary" heading over an empty list. The reader cannot tell a
  finding from a non-finding by its shape.
- A missing input is a missing input. `CompanyNameNeeded` exists precisely so
  an absent employer is not rendered as a result.
- Six cards on every scan spends output tokens the reasoning model draws from
  the same budget as its answer, and this project has already failed once from
  budget exhaustion.

`Official Registration` was retired outright on 2026-10-27, superseding the
"gated rather than removed" call this file used to record. Gating kept it alive
on a results set no query had aimed at registration — the `registration
certificate` query was dropped when the budget was three credits — so a posting
that *asserted* a registration got a card whose honest answer was "not
confirmed" by construction. A small employer's SEC filing is often unindexed,
a business is not required to be registered to hire honestly, and the
impersonation shape (a fake "CHED") is caught by `CLAIMED_TYPE=government` plus
Channel Match. Company Existence carries the identity question. See
`docs/decisions/verification-design.md`.
"""

import pytest

from app.models.schemas import VerifyRequest, VerificationItem
from app.services.scanner.verification_prompt import (
    VERIFY_CLAIM_CATEGORIES,
    VERIFY_RESPONSE_SCHEMA,
    _build_verify_prompt,
    expected_categories,
)


def req(**attributes) -> VerifyRequest:
    return VerifyRequest(company_name="Tanika", anomalies=[], attributes=attributes)


class TestEachCategoryIsGatedByItsClaim:
    """A category appears only when the posting made the claim it tests."""

    def test_existence_and_reputation_need_only_an_employer(self):
        # Both are about the employer, and the flow returns early without one.
        assert expected_categories(req()) == {"Company Existence", "Reputation"}

    def test_location_needs_a_stated_location(self):
        assert "Location / Branch" not in expected_categories(req())
        assert "Location / Branch" in expected_categories(req(LOCATION="Pampanga"))

    def test_channel_needs_a_stated_contact_channel(self):
        assert "Channel Match" not in expected_categories(req())
        assert "Channel Match" in expected_categories(req(CONTACT_METHOD="personal Gmail"))

    def test_a_stated_meeting_spot_is_also_a_channel(self):
        # Where to turn up is the channel the posting directs applicants to.
        assert "Channel Match" in expected_categories(req(MEETING_SPOT="Maingate Terminal"))

    def test_scheme_corroboration_needs_a_stated_reward(self):
        assert "Similar Offers" not in expected_categories(req())
        assert "Similar Offers" in expected_categories(req(PAY="300 daily"))

    def test_every_category_is_reachable(self):
        """A gate that can never open is a deleted category with extra steps."""
        reachable = expected_categories(
            req(
                LOCATION="Pampanga",
                CONTACT_METHOD="personal Gmail",
                MEETING_SPOT="Maingate Terminal",
                PAY="300 daily",
            )
        )
        assert reachable == set(VERIFY_CLAIM_CATEGORIES)

    def test_pay_alone_does_not_open_every_category(self):
        """The overcorrection: gating must not become "report everything"."""
        assert expected_categories(req(PAY="300 daily")) == {
            "Company Existence",
            "Reputation",
            "Similar Offers",
        }

    def test_a_blank_attribute_opens_nothing(self):
        # An empty value is the posting having said nothing. The parser omits
        # these already; this is the belt to that braces.
        assert expected_categories(req(LOCATION="   ", PAY="")) == {
            "Company Existence",
            "Reputation",
        }


class TestThePromptAsksForTheGatedSet:
    """The prompt must state which categories the posting made claims for."""

    def test_the_instruction_separates_reported_from_omitted(self):
        # Both lists appear in the prompt, and that is correct: naming the
        # omitted categories is the load-bearing part. A model asked for six and
        # told about three returns six.
        prompt = _build_verify_prompt(req(CONTACT_METHOD="personal Gmail"), "RESULTS")

        report_only, _ = prompt.split("DO NOT REPORT", 1)
        assert "Channel Match" in report_only
        assert "Location / Branch" not in report_only

    def test_the_omitted_categories_are_named_so_the_model_knows_to_omit(self):
        # Silence about a category reads as "not required", which is the
        # opposite of what is meant.
        prompt = _build_verify_prompt(req(CONTACT_METHOD="personal Gmail"), "RESULTS")
        _, do_not_report = prompt.split("DO NOT REPORT", 1)

        assert "Location / Branch" in do_not_report
        assert "nothing to test" in do_not_report
        # An omitted category must be distinguished from one that found nothing.
        # Collapsing them is the bug being fixed.
        assert "not a finding" in do_not_report
        assert "not a failure" in do_not_report

    def test_a_post_with_every_claim_is_told_to_report_everything(self):
        # No omissions, so no DO NOT REPORT block at all - and no "report all
        # five", which would re-introduce reporting a category with nothing to test.
        prompt = _build_verify_prompt(
            req(
                LOCATION="Pampanga",
                CONTACT_METHOD="personal Gmail",
                MEETING_SPOT="Maingate Terminal",
                PAY="300 daily",
            ),
            "RESULTS",
        )

        assert "DO NOT REPORT" not in prompt
        assert "Report every one of them" in prompt

    def test_the_claims_block_is_unaffected(self):
        prompt = _build_verify_prompt(req(CONTACT_METHOD="personal Gmail"), "RESULTS")
        assert "personal Gmail" in prompt

    def test_the_schema_enum_still_admits_every_category(self):
        # The enum is the vocabulary, not the expected set. Narrowing it would
        # break a stored result that already used one of the other values.
        enum = VERIFY_RESPONSE_SCHEMA["properties"]["checks"]["items"]["properties"][
            "category"
        ]["enum"]
        assert set(enum) == set(VERIFY_CLAIM_CATEGORIES)


class TestScoringUnchangedByGating:
    """Gating must not quietly become scoring. These lock both.

    The old scoring system (`risk_calculator`) is deleted. The assessment is a decision
    procedure over two axes, not a sum of weights. The tests below verified the
    old refutation scoring behavior and are kept as documentation of what was
    removed. They are now tombstones asserting the old functions are gone.
    """

    def test_the_old_refutation_scorer_is_gone(self):
        import importlib.util

        assert importlib.util.find_spec("app.services.scanner.risk_calculator") is None

    def test_the_old_ahp_weights_are_gone(self):
        from pathlib import Path
        script = Path(__file__).resolve().parents[1] / "scripts" / "derive_refutation_weights.py"
        assert not script.exists(), "scripts/derive_refutation_weights.py was deleted with the scoring model"


@pytest.mark.parametrize(
    "attributes,expected",
    [
        ({}, {"Company Existence", "Reputation"}),
        ({"LOCATION": "Manila"}, {"Company Existence", "Reputation", "Location / Branch"}),
    ],
)
def test_the_log_will_not_fire_a_false_alarm(attributes, expected):
    """`expected_categories` is what the missing-category log compares against.

    If this still expected all six, every posting without a location would log a
    missing `Location / Branch` — and a warning that fires on almost every
    request is a warning nobody reads.
    """
    assert expected_categories(req(**attributes)) == expected
    assert expected <= set(VERIFY_CLAIM_CATEGORIES)
