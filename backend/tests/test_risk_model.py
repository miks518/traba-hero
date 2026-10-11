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

import sys
from pathlib import Path

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
from app.services.scanner.risk_calculator import _LEGACY_LABEL_MAP

EX, REG, REP = "Company Existence", "Official Registration", "Reputation"
LOC, CHAN, SCHEME = "Location / Branch", "Channel Match", "Similar Offers"


def flag(severity):
    return Anomaly(flag="X", reasoning="r", severity=severity)


def check(label, status):
    return VerificationItem(label=label, status=status, explanation="e")


def posting(*severities):
    return _posting_risk_from_flags([flag(s) for s in severities])[0]


def verify(*pairs):
    """The employer stage, as the flow actually calls it.

    This used to reach `_calculate_risk_score_from_verify`, which nothing in
    production calls. Every property asserted below therefore described a
    function that had been superseded: the tests were green and the live stage
    was untested. It now calls `_refutation_score_from_verify`, which is what
    `verification_flow` invokes.

    Note the return: `None` for "nothing was refuted", not `0`. Two assertions
    below changed with the repointing -- an all-green and an all-yellow list
    scored `0` under the retired stage's scale and score `None` under the live
    one. That difference is the point of the stage, not an accident: `None` says
    nothing was learned, and `0` would read as a measurement of zero risk.
    """
    return _refutation_score_from_verify([check(*p) for p in pairs])


def final(posting_score, verify_score):
    return _combine_scores(posting_score, verify_score)[0]


# All six categories the design actually checks. The fixtures below used to
# carry only the three employer categories, which was enough when those were the
# whole vocabulary; since `Location / Branch`, `Channel Match` and `Scheme
# Corroboration` were added, "everything refuted" has meant three sixths of it,
# and `TestTheTotalIsBounded` stopped testing what its name claims.
ALL_CATEGORIES = (EX, REG, REP, LOC, CHAN, SCHEME)

def _derivation():
    """The AHP script, imported by path.

    It lives under `scripts/` rather than in the package because it is a
    derivation tool, not runtime code - `risk_calculator.py` does not import it
    and must not.
    """
    path = str(Path(__file__).resolve().parents[1] / "scripts")
    if path not in sys.path:
        sys.path.append(path)
    import derive_refutation_weights
    return derive_refutation_weights


ALL_GREEN = [(c, "green") for c in ALL_CATEGORIES]
NO_DATA = [(c, "yellow") for c in ALL_CATEGORIES]
REP_RED = [(c, "red" if c == REP else "green") for c in ALL_CATEGORIES]
ALL_RED = [(c, "red") for c in ALL_CATEGORIES]

# The three employer categories alone, kept because several tests are about what
# a legacy stored result does - an old verification carries only these labels.
LEGACY_RED = [(EX, "red"), (REG, "red"), (REP, "red")]


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

        The second assertion is what keeps this from passing vacuously. "Nothing
        was learned" is also what a stage that ignores every input returns, so
        the same list with one yellow turned red has to move the number. Without
        that, this test would be satisfied by a function that never looks at an
        item at all.
        """
        posting_score = posting("mid")
        mixed = [(EX, "green"), (REG, "yellow"), (REP, "yellow")]
        mixed_with_a_refutation = [(EX, "green"), (REG, "yellow"), (REP, "red")]

        assert verify(*mixed) is None
        assert final(posting_score, verify(*mixed)) == final(posting_score, None)
        assert final(posting_score, verify(*mixed_with_a_refutation)) > posting_score

    def test_two_unconfirmed_categories_contribute_nothing(self):
        posting_score = posting("mid")
        mixed = [(EX, "green"), (REG, "yellow"), (REP, "yellow")]

        # `None`, not 0. See `verify`'s docstring: a zero here would report a
        # measurement of zero risk rather than the absence of a measurement.
        assert verify(*mixed) is None
        assert final(posting_score, verify(*mixed)) == posting_score

    def test_green_never_contributes_either(self):
        """Green means a result stated a fact, not that the fact was reassuring."""
        posting_score = posting("mid")

        assert verify(*ALL_GREEN) is None


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


class TestTheCombinationOverTheLiveStage:
    """The numbers the combine step produces from the stage it really calls.

    Renamed from `TestWhatThePanelWillNowShow`. Every test in it ran against
    `_calculate_risk_score_from_verify`, a 0-100 category share on the retired
    scale, while the panel's number comes from `_refutation_score_from_verify`
    on a 0-50 refutation sum. The class asserted readings the live stage cannot
    produce -- `test_a_clean_posting_with_a_published_report` expected 35, which
    no combination of these inputs reaches -- and the name claimed the opposite.

    The final figures are unchanged by the rename: at posting 100 both readings
    are 100, and that is a property of the cap rather than a defect. A posting
    that has already maxed out is critical whether or not its employer is clean.
    """

    def test_three_high_flags_with_a_clean_employer(self):
        assert final(posting("high", "high", "high"), verify(*ALL_GREEN)) == 100

    def test_three_high_flags_with_a_published_report(self):
        assert final(posting("high", "high", "high"), verify(*REP_RED)) == 100

    def test_three_high_flags_with_nothing_found(self):
        assert final(posting("high", "high", "high"), verify(*NO_DATA)) == 100

    def test_a_clean_posting_with_a_published_report(self):
        """A posting with no indicators, at an employer with a published report.

        Worth pinning because it is the case the blend hid. The refuted
        Reputation claim stands entirely on its own here: the posting stage
        contributes nothing, so the whole number is the evidence stage's. It was
        35 under the retired share of a blend and is 10 under the live refutation
        weight -- and the direction of the change is the one that matters, since
        the number can no longer be pulled down by averaging it with a posting
        score of zero.
        """
        assert verify(*REP_RED) == REFUTATION_WEIGHTS["Reputation"]
        assert final(posting(), verify(*REP_RED)) == REFUTATION_WEIGHTS["Reputation"]
        assert _level_for(final(posting(), verify(*REP_RED))) == "low"


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
            "Similar Offers",
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
            "Similar Offers",
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
        """Results stored before the renames used 'SEC Registration' and 'Scheme
        Corroboration'. Without the mapping a stored verification silently
        rescores to the default of zero, which returns None - so a refuted claim
        reads as a stage that never ran.
        """
        for legacy, current in (
            ("SEC Registration", "Official Registration"),
            ("Scheme Corroboration", "Similar Offers"),
        ):
            items = [VerificationItem(label=legacy, status="red", explanation="")]

            assert _refutation_score_from_verify(items) == REFUTATION_WEIGHTS[current], legacy

    def test_a_legacy_label_is_not_mistaken_for_an_unknown_one(self):
        """The overcorrection of the mapping above.

        `unknown label -> 0` is a rule, and it is right: silence is not a score.
        The risk is that a *known* legacy label falls into it, and the cost is a
        category that renders with no weight behind it - which looks like a
        working check and is not.
        """
        items = [VerificationItem(label="Scheme Corroboration", status="red", explanation="")]

        assert _refutation_score_from_verify(items) is not None
        assert _refutation_score_from_verify(items) > 0

    def test_both_legacy_tables_agree(self):
        """`risk_calculator` and `verification_parser` each keep a copy.

        Two copies because the scoring module has to stay importable without
        pulling in the prompt. An alias in one and not the other is the worst
        shape: the category parses, renders, and scores zero.
        """
        from app.services.scanner.verification_parser import _LEGACY_LABELS

        assert _LEGACY_LABELS == {k: v.lower() for k, v in _LEGACY_LABEL_MAP.items()}

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


class TestTheLabelLookupIsCaseInsensitive:
    """A refutation written in the wrong case is still a refutation.

    The JSON schema's enum is title case and `verification_flow` goes through it,
    so the structured path cannot produce `channel match`. The labeled-text
    fallback can: `verification_parser` accepts whatever label it reads, and a
    model that writes `VERIFY: channel match` without the schema produces exactly
    that.

    Missed the table, it scored zero, `penalty` stayed at 0, and the stage
    returned `None`. A genuine refutation was silently discarded -- and that is
    the one direction of error worth being paranoid about, because the reader
    would be shown a posting that had been corroborated as clean.
    """

    def test_a_lowercase_category_scores_its_full_weight(self):
        items = [VerificationItem(label="channel match", status="red", explanation="")]

        assert _refutation_score_from_verify(items) == REFUTATION_WEIGHTS["Channel Match"]

    def test_every_category_survives_a_case_change(self):
        """Parametrised over the whole table, not the one label that was reported.

        Picking Channel Match alone would leave five keys that could still be
        exact-cased, and the same bug would ship for them.
        """
        for label, weight in REFUTATION_WEIGHTS.items():
            items = [VerificationItem(label=label.lower(), status="red", explanation="")]
            assert _refutation_score_from_verify(items) == weight, label

    def test_a_legacy_label_survives_a_case_change(self):
        items = [VerificationItem(label="sec registration", status="red", explanation="")]

        assert _refutation_score_from_verify(items) == REFUTATION_WEIGHTS["Official Registration"]

    def test_case_folding_does_not_invent_a_weight(self):
        """The overcorrection.

        Lowercasing the lookup key could have been done by lowercasing the table
        too and comparing loosely, which would let near-misses in. "Channel
        Match " with trailing whitespace is still the same label and still
        scores; "channel-match" is a different string and is still silence.
        """
        padded = [VerificationItem(label="Channel Match ", status="red", explanation="")]
        unknown = [VerificationItem(label="channel-match", status="red", explanation="")]

        assert _refutation_score_from_verify(padded) == REFUTATION_WEIGHTS["Channel Match"]
        assert _refutation_score_from_verify(unknown) is None

    def test_the_table_and_the_lookup_cannot_drift_apart(self):
        """`_REFUTATION_WEIGHTS_BY_LOWER` is derived, not restated.

        It is built at import from `REFUTATION_WEIGHTS`, so a weight added there
        is a weight this stage can find. Asserted on the sizes rather than on the
        dict: a lookup table missing a key is exactly the failure, and an equality
        check against itself would not notice a dropped entry.
        """
        from app.services.scanner.risk_calculator import _REFUTATION_WEIGHTS_BY_LOWER

        assert len(_REFUTATION_WEIGHTS_BY_LOWER) == len(REFUTATION_WEIGHTS)
        assert set(_REFUTATION_WEIGHTS_BY_LOWER) == {k.lower() for k in REFUTATION_WEIGHTS}


class TestTheRetiredEmployerStageIsStillExported:
    """The tombstone for the function the other tests used to assert through.

    `_calculate_risk_score_from_verify` is no longer on any production path --
    `verification_flow` calls `_refutation_score_from_verify` -- but
    `test_scanner_package.py` pins the package's symbol list, so it stays
    exported. Keeping one test pointed at it is deliberate: the reason it must
    not be deleted quietly is that something still imports it, and the way to
    find that out is to look.

    Its scale is a different one -- a share of the category weights normalised to
    100 -- so it is **not** a drop-in for the live stage. The contrast below is
    the whole point: the retired function scores an all-green verification at 0
    and the live one at `None`. Reading a passing test against the retired one as
    evidence that the evidence stage works is exactly the mistake these two
    classes exist to prevent.
    """

    def test_it_still_returns_the_retired_scale(self):
        items = [
            VerificationItem(label="Company Existence", status="green", explanation=""),
            VerificationItem(label="Official Registration", status="red", explanation=""),
        ]

        assert _calculate_risk_score_from_verify(items) == (25, "low")

    def test_it_is_not_the_live_stage(self):
        items = [
            VerificationItem(label="Company Existence", status="green", explanation=""),
            VerificationItem(label="Official Registration", status="red", explanation=""),
        ]

        assert _refutation_score_from_verify(items) == REFUTATION_WEIGHTS["Official Registration"]
        assert _calculate_risk_score_from_verify(items)[0] != _refutation_score_from_verify(items)

    def test_all_green_is_zero_on_the_retired_stage_and_absent_on_the_live_one(self):
        items = [check(*pair) for pair in ALL_GREEN]

        assert _calculate_risk_score_from_verify(items)[0] == 0
        assert _refutation_score_from_verify(items) is None

class TestTheEvidenceWeightsAreDerivedNotChosen:
    """The claim in the module comment, re-checked on every run.

    `REFUTATION_WEIGHTS` used to be judgement, and `SCORING-SOURCES.md` section 8
    flagged it as the one number in the file with no method behind it. A comment
    saying a weight is derived from a pairwise matrix is worth nothing if nothing
    re-derives it, so the matrix, the eigenvector, the consistency ratio and the
    rounding are all recomputed here from the same judgment list the script uses.
    """

    def test_the_derivation_script_is_importable_without_numpy(self):
        """No `importorskip`. That call skips silently on a clean install,
        because numpy is not in `requirements.txt`, and a guardrail that quietly
        stops running is worse than one that is absent - it reads as coverage."""
        assert _derivation().CRITERIA

    def test_the_weights_match_the_matrix_the_script_would_use(self):
        derive = _derivation()

        matrix = derive.build_matrix()
        eigenvector = derive.principal_eigenvector(matrix)
        _, _, cr = derive.consistency(matrix, eigenvector)

        # PASS against Saaty's threshold. Without this the weights are only
        # *reproducible*, not defensible: a matrix can be self-consistent about a
        # judgment nobody would accept.
        assert cr < derive.CR_THRESHOLD, f"CR {cr:.4f} exceeds {derive.CR_THRESHOLD}"

        points = derive.anchor_to_points(eigenvector, "Channel Match", 25)
        derived = dict(zip(derive.CRITERIA, points))

        assert derived == REFUTATION_WEIGHTS, (
            "the weights in risk_calculator.py no longer match the pairwise "
            "matrix; re-run scripts/derive_refutation_weights.py and update both"
        )

    def test_the_hierarchy_is_the_one_the_weights_claim(self):
        """A set of numbers does not say what they mean; the ordering does.

        This is the part worth defending. The matrix may be argued with, but if
        the argument reorders these, the weights change and this fails - which is
        the point. A silent reorder would keep the numbers valid and change the
        scoring.
        """
        ordered = sorted(REFUTATION_WEIGHTS.items(), key=lambda kv: kv[1], reverse=True)
        labels = [label for label, _ in ordered]

        assert labels[:4] == [
            "Channel Match",
            "Similar Offers",
            "Reputation",
            "Location / Branch",
        ]
        # The bottom two are equal on judgment, so they must be equal in weight.
        assert REFUTATION_WEIGHTS["Company Existence"] == REFUTATION_WEIGHTS["Official Registration"]

    def test_the_bottom_two_can_still_move_a_score(self):
        """The overcorrection.

        AHP widened the spread to 12.5x, which is what drove these two to 2. That
        is defensible as a *proportion* but not as a *dead* number: a refuted
        Official Registration has to be able to change the level band, or the
        derived weights silently disabled a check the panel still renders.
        """
        posting_score = posting("high")

        low = final(posting_score, verify((EX, "green"), (REG, "green"), (REP, "green")))
        refuted = final(posting_score, verify((EX, "green"), (REG, "red"), (REP, "green")))

        assert refuted > low, "a refuted registration claim must move the number"

class TestTheDocumentedSensitivityIsReal:
    """SCORING-SOURCES.md section 9 states a stability interval. Check it.

    A table in a document that nothing computes is a claim, not a result. These
    recompute it at run time, so a weight change that quietly narrows the stable
    range fails here instead of reaching a defence with a number nobody checked.
    """

    CASES = [
        ("clean", 0, ["Channel Match"]),
        ("one_red", 12, ["Channel Match"]),
        ("three_red", 12, ["Channel Match", "Similar Offers", "Reputation"]),
        ("two_highs", 80, ["Channel Match", "Similar Offers"]),
        ("at_cap", 100, ["Channel Match"]),
        ("all_six", 12, None),
    ]

    def _levels(self, anchor):
        derive = _derivation()
        weights = derive.principal_eigenvector(derive.build_matrix())
        points = derive.anchor_to_points(weights, "Channel Match", anchor)
        table = dict(zip(derive.CRITERIA, points))

        out = {}
        for name, posting, cats in self.CASES:
            categories = cats or derive.CRITERIA
            penalty = min(MAX_REFUTATION_SCORE, sum(table[c] for c in categories))
            out[name] = _level_for(min(100, posting + penalty))
        return out

    def test_the_stable_plateau_is_twenty_five_to_thirty(self):
        at_25 = self._levels(25)
        at_30 = self._levels(30)

        assert at_30 == at_25, "the upper plateau boundary moved"
        # The plateau starts AT the chosen anchor, not below it. This was
        # originally written as 20-30 and failed: at 20 the three-red case reads
        # moderate rather than high. The distinction is the whole point - an
        # anchor at the lower edge and one in the middle of a plateau are not the
        # same claim, and only one of them is true here.
        assert self._levels(20) != at_25, "the lower boundary moved above 25"

    def test_the_two_boundaries_fail_in_opposite_directions(self):
        """Why the anchor is set where it is.

        Below 25 the three-red case understates - it drops out of `high`. Above
        30 a clean posting is overstated - it is lifted out of `low`. Setting
        the anchor at 25 means the reachable error in a live deployment is
        understatement, never overstatement, which is the right direction for a
        tool whose output is read as advice about money.
        """
        at_25 = self._levels(25)

        assert self._levels(20)["three_red"] == "moderate"
        assert at_25["three_red"] == "high"
        assert self._levels(35)["clean"] == "moderate"
        assert at_25["clean"] == "low"

    def test_the_chosen_anchor_leaves_a_clean_posting_clean(self):
        """The asymmetry the whole model exists to enforce.

        A refuted Channel Match is the strongest single signal the retrieval can
        produce, and it must still not move a posting that reported nothing into
        a band that reads as 'moderate'. Verification withholds trust; it never
        grants or manufactures it.
        """
        assert self._levels(25)["clean"] == "low"
