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

    def test_it_keeps_registration_broader_than_the_sec(self):
        low = text.lower()
        for body in ("dti", "peza", "boi", "local government unit"):
            assert body in low, body

    def test_the_recommendation_is_addressed_to_a_job_seeker(self):
        """A reader needs a way to respond to an offer, not a compliance task."""
        low = text.lower()
        assert "addressed to a job seeker" in low
        assert "do not tell them to check a registry" in low
