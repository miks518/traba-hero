"""VERIFY_PROMPT.md is the prompt the backend actually loads.

`VERIFY_SYSTEM_PROMPT` was a string constant in `verification_prompt.py`, so
editing a prompt meant editing Python and restarting the server. Every other
endpoint's prompt already loads from a file in `backend/`, and this one is the
longest of them — the rules about what may be claimed are the libel guardrail,
so they need to be readable and diffable in a text file rather than buried in a
module docstring-adjacent constant.

The load-bearing property is that the file is the source of truth, not a copy.
A prompt that lives in two places drifts, and this project's whole guardrail set
has drifted before: `SYSTEM_PROMPT.md` and `prompts.py`'s field rules held
different rules about flagging the absence of something, and only the Python
copy had the fix.
"""

from pathlib import Path

from app.services.scanner.verification_prompt import (
    VERIFY_SYSTEM_PROMPT,
    load_verify_prompt,
)

PROMPT = Path(__file__).resolve().parents[1] / "VERIFY_PROMPT.md"
MODULE = Path(__file__).resolve().parents[1] / "app/services/scanner/verification_prompt.py"

text = PROMPT.read_text(encoding="utf-8")
source = MODULE.read_text(encoding="utf-8")


class TestTheFileIsTheSource:
    def test_the_file_exists_and_is_not_empty(self):
        assert text.strip(), "VERIFY_PROMPT.md is empty"

    def test_the_loaded_prompt_comes_from_the_file(self):
        """Not from the fallback: the two must not silently diverge."""
        assert VERIFY_SYSTEM_PROMPT.strip() == text.strip()

    def test_the_fallback_is_a_copy_of_the_file_and_not_an_older_revision(self):
        """The drift this repo has already had once, closed.

        `_FALLBACK_VERIFY_PROMPT` is a second copy of the longest prompt in the
        project, and nothing compared it to the file. Editing the file alone
        left the fallback holding a prompt that had since dropped a rule — and
        the tests above read the *file*, so they stayed green the whole time. The
        deployment that hits this is the one with no `VERIFY_PROMPT.md`: the copy
        nobody edits, serving rules nobody re-reads.
        """
        from app.services.scanner.verification_prompt import _FALLBACK_VERIFY_PROMPT

        assert _FALLBACK_VERIFY_PROMPT.strip() == text.strip()

    def test_the_file_wins_over_the_in_module_copy(self, monkeypatch, tmp_path):
        """Proof the file is the source and the constant is only a fallback.

        Not "the prose is absent from the module" — the fallback deliberately
        carries a full copy, because a deployment shipping without the file must
        not verify against a stub. What matters is which one is *used*, so this
        points the loader at a different file and checks the result follows it.
        """
        replacement = tmp_path / "VERIFY_PROMPT.md"
        replacement.write_text("SENTINEL PROMPT", encoding="utf-8")
        monkeypatch.setattr(
            "app.services.scanner.verification_prompt.PROMPT_PATH", replacement
        )

        assert load_verify_prompt() == "SENTINEL PROMPT"


class TestTheFallbackIsTheSameRules:
    """The module keeps a fallback for when the file is missing.

    A deployment that ships without the file must not silently verify against a
    one-line stub — that is how a guardrail disappears without a trace. The
    fallback therefore has to carry the rules, not just a role.
    """

    def test_the_fallback_exists_and_is_substantial(self):
        fallback = load_verify_prompt.__doc__ or ""
        # The loader returns the constant when the file is unreadable; check the
        # constant itself is the guarded prompt rather than a stub.
        assert len(VERIFY_SYSTEM_PROMPT) > 500
        assert fallback

    def test_a_missing_file_yields_the_guarded_prompt_not_a_stub(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "app.services.scanner.verification_prompt.PROMPT_PATH", tmp_path / "absent.md"
        )
        loaded = load_verify_prompt()

        assert "OUTPUT RULES" in loaded
        assert "Never write that a company" in loaded

    def test_an_empty_file_yields_the_guarded_prompt(self, monkeypatch, tmp_path):
        empty = tmp_path / "VERIFY_PROMPT.md"
        empty.write_text("   \n", encoding="utf-8")
        monkeypatch.setattr(
            "app.services.scanner.verification_prompt.PROMPT_PATH", empty
        )

        assert "OUTPUT RULES" in load_verify_prompt()


class TestTheGuardrailsSurvivedTheMove:
    """Re-assert the rules in the file the backend now loads.

    These are duplicated from `verification_prompt.py`'s own test module on
    purpose: a move that dropped a rule would still pass every other test, and
    this project's cost for losing one is a legal claim rather than a bug.
    """

    def test_it_asks_for_json_so_a_schema_less_model_still_answers_in_json(self):
        assert "JSON" in text

    def test_a_different_channel_is_reported_as_facts_and_decided_by_code(self):
        """The PAF case is why the category exists; the Gmail case is why the
        model no longer decides it.

        A Philippine Airforce posting linked to `paf-recruitment-portal.ph`; the
        real PAF site is `paf.mil.ph`. The model had the contradiction in its own
        sentence and reported yellow. The first fix told the model that any
        different channel was red, which overcorrected: a real employer using a
        Gmail address became a contradiction too. The prompt now asks for the
        facts and says outright that the server assigns the status.
        """
        low = text.lower()
        assert "do not decide a status for this category" in low
        assert "the server compares the lists and assigns the status" in low
        assert "a different channel is not automatically a contradiction" in low
        assert "a free email address is ordinary in philippine job postings" in low
        assert "a government office using a domain outside .gov.ph" in low
        assert "a domain that imitates the company's own" in low
        assert 'do not write a channel match entry in "checks"' in low

    def test_channel_match_names_the_rules_the_server_applies(self):
        """The prompt must describe the same rules the code applies.

        The rules live in `channel_match.py`, and this is the prose half. A
        prompt that still said "any different channel is red" would ask the model
        to report facts under a rule the code no longer follows.
        """
        low = text.lower()
        assert "a government office using a domain outside .gov.ph" in low
        assert "a domain that imitates the company's own, is a contradiction" in low
        assert "a free email address at a company the results confirm is not" in low

    def test_the_model_is_not_asked_for_a_channel_status_or_a_level(self):
        """Both decisions are code-owned, and the prompt says so.

        The model still writes the report and the recommendation, but the overall
        level and the Channel Match status come from `assessment.py` and
        `channel_match.py`. If the prompt asked for either, the schema would drop
        it and the model's answer would carry a field the flow ignores - the
        half-wired shape this split exists to remove.
        """
        low = text.lower()
        assert "do not return a risk level or a risk score" in low
        assert "the server computes both" in low
        assert "never put a status in this object" in low

    def test_status_is_decided_across_categories_not_within_them(self):
        """The general form of the fix. A contradiction is a relation between
        two facts; a green in one category does not retire a red in another."""
        low = text.lower()
        assert "decide each status against all the results you were given" in low
        assert "does not disappear because the first is reassuring" in low

    def test_the_absence_prohibition_is_not_weakened_by_any_of_this(self):
        """The overcorrection, and the thing a panel would check. Everything
        added above sharpens when `red` applies. Nothing added may make `red`
        easier to reach in general — "we found nothing" must stay yellow."""
        low = text.lower()
        assert "absence of a result is never red" in low
        assert "never red because nothing was found" in low
        assert "never write that a company" in low
    def test_an_empty_reputation_leaves_the_finding_empty(self):
        """The one category whose unconfirmed finding is suppressed.

        Every other category can say something useful when the results are empty,
        because its finding is about the employer's footprint. Reputation could
        only restate the absence, and it did so as a sentence naming "scam
        reports" and "fraud warnings" beside a named company — reader-facing text
        putting the two banned words next to a real business in order to report
        nothing. The panel hides the card, so if this rule is dropped the card
        simply renders that sentence again with nothing behind it.
        """
        low = text.lower()
        assert "leave the `finding` for this category empty" in low
        assert "rather than writing that none were found" in low

    def test_the_empty_finding_is_scoped_to_reputation_alone(self):
        """The overcorrection. A rule generalised to every category would empty
        the panel: an unconfirmed Company Existence is the finding that tells a
        reader their employer has no online footprint, and it must still be
        written."""
        low = text.lower()
        assert "this applies to this category only" in low
        assert "the other four have a finding worth stating" in low

    def test_an_empty_finding_is_not_a_way_to_skip_a_real_one(self):
        """The failure mode of an instruction the model can satisfy cheaply: it
        returns empty for a company that plainly has reviews, and a complaint on
        the record goes unreported. That is the case the rule must not license."""
        low = text.lower()
        assert "if any result does describe a complaint" in low
        assert "never a way to avoid writing it" in low

    def test_the_general_yellow_rule_points_at_the_exception(self):
        """`finding` still says "on yellow, say plainly that the results do not
        mention this category". Left alone, that contradicts the Reputation rule
        and the model has to choose between them."""
        low = text.lower()
        assert "except reputation, which is left empty instead" in low

    def test_it_names_every_output_key(self):
        for key in ("checks", "evidence", "report", "recommendation"):
            assert key in text, key

    def test_it_treats_search_results_as_untrusted_data(self):
        assert "untrusted" in text.lower()

    def test_it_bans_the_accusatory_words(self):
        """The panel states facts about a named company, so the model may not
        call one a scam, a fraud, or a criminal — that is the libel exposure."""
        low = text.lower()
        assert "never write that a company" in low
        assert "scam, a fraud, or a criminal" in low

    def test_it_bans_inference_and_absolute_words(self):
        """The words are listed *in* a prohibition, so they appear in the text.

        Asserting their absence would pass vacuously — the ban is the only reason
        they are there. What is checked is that each family of banned words is
        actually named.
        """
        low = text.lower()
        assert "do not guess at intent" in low
        for word in ("likely", "appears", "suggests", "probably", "seemingly", "we think"):
            assert word in low, f"{word} is no longer in the banned list"
        assert "do not use absolutes" in low
        for word in ("always", "never", "definitely", "100%"):
            assert word in low, f"{word} is no longer in the banned absolutes"

    def test_it_says_absence_is_never_red(self):
        assert "Absence of a result is NEVER red" in text

    def test_the_prompt_does_not_still_ask_for_a_registration_check(self):
        """Tombstone for the retired category.

        `Official Registration` was removed because the search never sought its
        evidence: a gated card over a generic result set answered "not
        confirmed" by construction. Its absence is pinned, in both copies via
        the fallback-equality test above, so it cannot drift back in as a
        half-remembered rule.
        """
        low = text.lower()
        for body in ("official registration", "dti", "peza", "boi"):
            assert body not in low, body

    def test_the_recommendation_is_addressed_to_a_job_seeker(self):
        """A reader needs a way to respond to an offer, not a compliance task."""
        low = text.lower()
        assert "addressed to a job seeker" in low
        assert "do not tell them to check a registry" in low

    def test_the_six_categories_are_a_vocabulary_and_not_a_quota(self):
        """The system prompt must not outrank the request's gating instruction.

        The request tells the model which categories to report and which to omit,
        and that only works if the system prompt does not also say "report on
        exactly these six". Two instructions in the same request, one of them
        telling the model to ignore the other, is how the gating gets silently
        undone — and the six placeholder cards come back with no error anywhere.
        """
        low = text.lower()

        assert "exactly these six" not in low
        assert "include all six" not in low
        assert "not a quota" in low
        # The system prompt's half of the deferral. The literal DO NOT REPORT
        # list is in the per-request gating instruction, which
        # `test_claim_gating.py` covers — this is about the file the backend
        # loads not overriding it.
        assert "told to report and no others" in low
