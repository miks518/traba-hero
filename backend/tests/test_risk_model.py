"""The two-stage risk model: posting indicators plus a verification penalty.

It used to be a 60/40 blend, and three things were wrong with it. At a maxed
posting (three high-severity flags, 100), a clean employer record pulled the
number to 60 â€” clean verification was able to halve a posting that had already
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

The evidence stage has since been renamed to what it actually measures: it
scores *refutations*. A `red` now means a retrieved source contradicts a
specific claim the posting made, so a `green` means the claim was confirmed by
a source and a `yellow` means nothing was learned either way. Only `red` scores.
Confirmation and silence both cost zero, because verification withholds trust
and never grants it. The classes below cover that stage; the older ones above
still cover the properties of the two-stage model that survived the rename.
"""

import pytest

from app.models.schemas import Anomaly, VerificationItem
from app.services.scanner.risk_calculator import (
    MAX_REFUTATION_SCORE,
    REFUTATION_WEIGHTS,
    _calculate_risk_score_from_verify,
    _combine_scores,
    _level_for,
    _posting_risk_from_flags,
    _refutation_score_from_verify,
)

EX, REG, REP = "Company Existence", "Official Registration", "Reputation"


def flag(severity):
    return Anomaly(flag="X", reasoning="r", severity=severity)


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
        """Under the blend these were 74 and 60 â€” 14 apart, and near-reversed
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


class TestRefutationScoring:
    """Points require a source that contradicts a claim.

    The three-state model: confirmed adds nothing, a contradiction adds, and
    nothing learned adds nothing. Silence scoring points would penalise a sole
    proprietorship with no web presence - the ordinary case in the Philippines
    and the population this product exists for.

    The weights are provisional - chosen on judgement, not derived by Saaty's
    pairwise method the way the posting weights were. So these tests assert
    *relationships* (this claim outweighs that one) and the behaviour of the
    stage, never that a particular weight is the right one.
    """

    def test_a_confirmed_claim_adds_nothing(self):
        items = [VerificationItem(label="Company Existence", status="green", explanation="")]
        assert _refutation_score_from_verify(items) is None

    def test_an_unverified_claim_adds_nothing(self):
        items = [VerificationItem(label="Company Existence", status="yellow", explanation="")]
        assert _refutation_score_from_verify(items) is None

    def test_a_refuted_channel_adds_points(self):
        """Channel Match is the impersonation check and carries the most weight."""
        items = [VerificationItem(label="Channel Match", status="red", explanation="")]
        assert _refutation_score_from_verify(items) == REFUTATION_WEIGHTS["Channel Match"]

    def test_a_refuted_location_carries_less_than_a_channel(self):
        weights = REFUTATION_WEIGHTS
        assert weights["Channel Match"] > weights["Location / Branch"]

    def test_every_known_claim_category_outscores_the_weakest(self):
        """A label with no weight at all would score 0 for being unrecognised.

        This is what separates a stored label the table does not know (which
        falls back to 0 and returns None - indistinguishable from silence) from
        a claim this design does check.
        """
        assert set(REFUTATION_WEIGHTS) == {
            "Channel Match",
            "Scheme Corroboration",
            "Reputation",
            "Location / Branch",
            "Company Existence",
            "Official Registration",
        }
        assert all(w > 0 for w in REFUTATION_WEIGHTS.values())

    def test_all_yellow_is_absent_not_zero(self):
        """None is not 0. It tells the caller nothing was learned, which a zero
        score would report as a measurement of zero risk."""
        items = [
            VerificationItem(label="Company Existence", status="yellow", explanation=""),
            VerificationItem(label="Channel Match", status="yellow", explanation=""),
        ]
        assert _refutation_score_from_verify(items) is None

    def test_an_empty_list_is_absent(self):
        assert _refutation_score_from_verify([]) is None

    def test_a_contradicted_claim_outranks_a_confirmed_one(self):
        """The comparison the rename was for, in the shape the panel shows it.

        Under the old employer-category model a `green` was worth zero because it
        meant "a result stated a fact, not that the fact was reassuring". Now a
        green means a source *confirms the claim*, so the meaningful assertion is
        that a contradiction is worth more than the confirmation sitting beside it.
        """
        confirmed = [VerificationItem(label="Channel Match", status="green", explanation="")]
        refuted = [VerificationItem(label="Channel Match", status="red", explanation="")]

        assert _refutation_score_from_verify(confirmed) is None
        assert _refutation_score_from_verify(refuted) == REFUTATION_WEIGHTS["Channel Match"]

    def test_the_stage_is_capped_at_fifty(self):
        """Asserts the cap *binds*, not merely that the result is under a number.

        `score <= MAX_REFUTATION_SCORE` compares the code against itself: raise the
        constant to 200 and the same five refutations score 64, which is still
        "under the cap". What has to hold is that the declared cap is below what
        the weights can actually produce, and that the produced number is the cap.

        The literal 50 is asserted rather than the constant. `MAX_REFUTATION_SCORE`
        *is* what the implementation compares against, so asserting it equals the
        constant is the same tautology — a change to either side moves both, and
        the test stays green while the cap moves. The spec fixes the share: the
        evidence stage may contribute at most half the scale, so the number is
        pinned and the constant has to follow it.
        """
        labels = [
            "Channel Match",
            "Location / Branch",
            "Reputation",
            "Scheme Corroboration",
            "Company Existence",
        ]
        items = [VerificationItem(label=label, status="red", explanation="") for label in labels]
        uncapped = sum(REFUTATION_WEIGHTS[label] for label in labels)

        assert MAX_REFUTATION_SCORE == 50
        assert uncapped > MAX_REFUTATION_SCORE
        assert _refutation_score_from_verify(items) == MAX_REFUTATION_SCORE

    def test_uncapped_refutations_accumulate_before_the_cap(self):
        """Two refuted claims are worth more than one, below the cap.

        Without this, summing could be replaced by taking the largest weight and
        the cap test above would still pass.
        """
        one = [VerificationItem(label="Location / Branch", status="red", explanation="")]
        two = one + [VerificationItem(label="Reputation", status="red", explanation="")]

        assert _refutation_score_from_verify(two) > _refutation_score_from_verify(one)
        assert _refutation_score_from_verify(two) == (
            REFUTATION_WEIGHTS["Location / Branch"] + REFUTATION_WEIGHTS["Reputation"]
        )

    def test_a_legacy_category_label_still_scores(self):
        """Results stored before the rename used 'SEC Registration'. Without the
        mapping a stored verification silently rescores to the default of zero,
        which returns None - so a refuted claim reads as a stage that never ran.
        """
        items = [VerificationItem(label="SEC Registration", status="red", explanation="")]

        assert _refutation_score_from_verify(items) == REFUTATION_WEIGHTS["Official Registration"]

    def test_an_unknown_label_is_silence_not_a_default_weight(self):
        """Absence of a weight is not a score.

        A label this design never asked about cannot be described as refuted, so
        it must not borrow a weight the way the old table's default of 10 did.
        """
        items = [VerificationItem(label="Something New", status="red", explanation="")]

        assert _refutation_score_from_verify(items) is None


class TestCombineScoresHasAFloor:
    """A search result may add to the posting's score. It may never lower it.

    The 60/40 blend was deleted because averaging let corroborating evidence
    outvote the artifact the reader asked about, and because 'we found nothing'
    could pull a maxed posting down. A plain 50/50 mean would reintroduce both:
    three high-severity anomalies plus an unlookable employer would score 50,
    reporting the most dangerous input this product receives as moderate.
    """

    def test_evidence_can_raise(self):
        assert _combine_scores(20, 30) == (50, "moderate")

    def test_evidence_cannot_lower_a_maxed_posting(self):
        score, level = _combine_scores(100, 0)
        assert score == 100
        assert level == "critical"

    def test_a_clean_employer_cannot_lower_a_finding_posting(self):
        assert _combine_scores(40, 0) == (40, "moderate")

    def test_an_absent_stage_leaves_the_posting_alone(self):
        assert _combine_scores(40, None) == (40, "moderate")

    def test_a_posting_with_no_findings_scores_only_from_refutation(self):
        assert _combine_scores(0, 30) == (30, "low")

    def test_both_absent_is_absent(self):
        assert _combine_scores(None, None) == (None, None)

    def test_no_combination_of_stages_scores_below_the_posting(self):
        """The floor as a property over the whole input range, not three examples.

        `max(posting, posting + refutation)` cannot go below the posting for any
        non-negative refutation, so this sweeps rather than samples.
        """
        for posting_score in range(0, 101, 5):
            for refutation_score in (0, 1, 6, 25, 50):
                assert _combine_scores(posting_score, refutation_score)[0] >= posting_score

    def test_a_whole_evidence_stage_still_fits_under_the_ceiling(self):
        """Evidence may raise the number, but never past 100.

        The posting stage caps at 100 and the refutation stage at 50, so a maxed
        posting plus a fully refuted employer is still critical rather than
        off the scale.
        """
        assert _combine_scores(100, MAX_REFUTATION_SCORE) == (100, "critical")
