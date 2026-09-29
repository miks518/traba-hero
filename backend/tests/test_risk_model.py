"""The two-stage risk model: posting indicators plus a verification penalty.

It used to be a 60/40 blend, and three things were wrong with it. At a maxed
posting (three high-severity flags, 100), a clean employer record pulled the
number to 60 — clean verification was able to halve a posting that had already
maxed out. A published scam report added only 14 points over that clean record,
so negative evidence moved the number far less than absence of it. And "we
found nothing at all" scored 100, tying "three damning categories".

The model is now additive and asymmetric: verification can only raise the
posting's score, never lower it. That is the property these tests exist to pin,
because the failure it prevents is a dangerous posting reading as a mild one.

The other load-bearing property is that **absence contributes nothing**. Under a
blend, yellow carried half weight because it needed to drag an average down. It
cannot carry weight here without penalising a check that found nothing, which
is the thing this project has repeatedly refused to do.
"""

import pytest

from app.models.schemas import RedFlag, VerificationItem
from app.services.scanner.risk_calculator import (
    _calculate_risk_score_from_verify,
    _combine_scores,
    _level_for,
    _posting_risk_from_flags,
)

EX, REG, REP = "Company Existence", "Official Registration", "Reputation"


def flag(severity):
    return RedFlag(flag="X", reasoning="r", severity=severity)


def check(label, status):
    return VerificationItem(label=label, status=status, explanation="e")


def posting(*severities):
    return _posting_risk_from_flags([flag(s) for s in severities])[0]


def verify(*pairs):
    return _calculate_risk_score_from_verify([check(*p) for p in pairs])[0]


def final(posting_score, verify_score):
    return _combine_scores(posting_score, verify_score)[0]


ALL_GREEN = [(EX, "green"), (REG, "green"), (REP, "green")]
NO_DATA = [(EX, "yellow"), (REG, "yellow"), (REP, "yellow")]
REP_RED = [(EX, "green"), (REG, "green"), (REP, "red")]
ALL_RED = [(EX, "red"), (REG, "red"), (REP, "red")]


class TestVerificationCannotLowerAPosting:
    @pytest.mark.parametrize("count", [1, 2, 3, 5])
    def test_a_clean_employer_never_reduces_a_high_scoring_posting(self, count):
        posting_score = posting(*(["high"] * count))
        before = final(posting_score, None)

        assert final(posting_score, verify(*ALL_GREEN)) >= before

    def test_a_maxed_posting_stays_maxed_under_a_clean_record(self):
        """The 60/40 blend turned three high-severity flags into a 60."""
        posting_score = posting("high", "high", "high")

        assert posting_score == 100
        assert final(posting_score, verify(*ALL_GREEN)) == 100


class TestNegativeEvidenceRaises:
    def test_a_published_report_raises_the_number(self):
        posting_score = posting("mid", "mid")
        before = final(posting_score, None)

        assert final(posting_score, verify(*REP_RED)) > before

    def test_a_negative_finding_outranks_a_clean_one(self):
        """Under the blend these were 74 and 60 — 14 apart, and near-reversed
        against a company we merely knew existed.

        Compared below the cap, because at posting 100 both readings are 100 and
        the number cannot express the difference. That is a property of the cap,
        not a defect: a posting that has already maxed out is critical whether or
        not its employer is clean, and the panel still shows the red card.
        """
        posting_score = posting("mid", "mid")

        assert final(posting_score, verify(*REP_RED)) > final(posting_score, verify(*ALL_GREEN))
        assert final(posting_score, verify(*ALL_GREEN)) == final(posting_score, None)


class TestAbsenceContributesNothing:
    def test_no_data_does_not_change_the_number(self):
        posting_score = posting("high", "mid")

        assert verify(*NO_DATA) is None
        assert final(posting_score, verify(*NO_DATA)) == final(posting_score, None)

    def test_partial_information_does_not_change_the_number(self):
        """One category confirmed, two unknown, is still mostly absence.

        Half-weight yellow existed to pull a blend's average down. Added to the
        posting it would penalise checks that found nothing, which is what this
        project refuses to do. Under the blend this exact set scored 29.

        The set has to be a *mix*: a list of one green item contains no yellow at
        all, so it would pass whether yellow carried weight or not.
        """
        posting_score = posting("mid")
        mixed = [(EX, "green"), (REG, "yellow"), (REP, "yellow")]

        assert final(posting_score, verify(*mixed)) == final(posting_score, None)

    def test_two_unconfirmed_categories_contribute_nothing(self):
        posting_score = posting("mid")
        mixed = [(EX, "green"), (REG, "yellow"), (REP, "yellow")]

        assert verify(*mixed) == 0
        assert final(posting_score, verify(*mixed)) == posting_score

    def test_green_never_contributes_either(self):
        """Green means a result stated a fact, not that the fact was reassuring."""
        posting_score = posting("mid")

        assert verify(*ALL_GREEN) == 0


class TestTheTotalIsBounded:
    def test_it_never_exceeds_one_hundred(self):
        assert final(100, verify(*ALL_RED)) == 100
        assert final(80, verify(*ALL_RED)) == 100

    def test_a_missing_stage_is_absent_rather_than_zero(self):
        """Unchanged from the blend, and still the rule that matters most.

        A posting nobody could look up is not penalised for the failed lookup,
        and a posting with no indicators is not raised by a clean record.
        """
        assert final(40, None) == 40
        assert final(None, 65) == 65
        assert final(None, None) is None

    def test_the_level_follows_the_number(self):
        assert _level_for(final(posting("high", "high", "high"), verify(*ALL_RED))) == "critical"
        assert _level_for(final(posting("low"), None)) == "low"


class TestWhatThePanelWillNowShow:
    """The numbers behind a verdict, kept as tests because they were wrong once.

    These are the readings a reader is shown, and the previous model produced
    "no data" and "three damning categories" at the same 100.
    """

    def test_three_high_flags_with_a_clean_employer(self):
        assert final(posting("high", "high", "high"), verify(*ALL_GREEN)) == 100

    def test_three_high_flags_with_a_published_report(self):
        assert final(posting("high", "high", "high"), verify(*REP_RED)) == 100

    def test_three_high_flags_with_nothing_found(self):
        assert final(posting("high", "high", "high"), verify(*NO_DATA)) == 100

    def test_a_clean_posting_with_a_published_report(self):
        """A posting with no indicators, at an employer with a scam report.

        Worth pinning because it is the case the blend hid: 0.6*0 + 0.4*35 was a
        rounding error, so the employer finding was effectively discarded.
        """
        assert final(posting(), verify(*REP_RED)) == 35
        assert _level_for(35) == "moderate"
