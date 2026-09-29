"""The shipped `.env.example` must actually load.

`.env.example` is the first thing a new deployment copies, and nothing else in
the repo executes it — so a typo, a missing knob, or a value pydantic cannot
parse sits there until someone installs the backend and the process dies at
import with a validation error pointing at a field they have never heard of.

It shipped with `AI_RESONING_ENABLED=` blank against a `bool | None` field, so
a fresh copy crashed on startup while the file's own comment said to leave it
blank. This parses the example the way a real deployment would.
"""

import pathlib

import pytest
from pydantic import ValidationError

from app.config import Settings

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / ".env.example"


class TestTheExampleFileLoads:
    def test_the_shipped_example_parses(self):
        """A blank line must mean "not set", never "invalid".

        Asserts the file *loads*, not what any particular knob is set to. Pinning
        a value here would be a change detector: it fails whenever a default is
        deliberately retuned, and says nothing about whether the example works.
        The defaults themselves are covered against the class, in each knob's
        own test.
        """
        Settings(_env_file=EXAMPLE)

    @pytest.mark.parametrize(
        "line,expected",
        [
            ("AI_REASONING_ENABLED=", None),
            ("AI_REASONING_ENABLED=   ", None),
            ("AI_REASONING_ENABLED=false", False),
            ("AI_REASONING_ENABLED=true", True),
        ],
    )
    def test_a_blank_optional_bool_reads_as_unset(
        self, tmp_path, monkeypatch, line, expected
    ):
        """`AI_REASONING_ENABLED=` is what a fresh copy ships with.

        The field is `bool | None`, and a blank string is not a bool. Reading
        blank as unset is what makes the file's instruction — "only sent when
        set, so leave blank" — actually true.
        """
        # A real OS variable outranks both the file and the class default, so a
        # developer who exported this would make these tests pass or fail on
        # their shell rather than on the parsing.
        monkeypatch.delenv("AI_REASONING_ENABLED", raising=False)
        env = tmp_path / ".env"
        env.write_text(line, encoding="utf-8")

        assert Settings(_env_file=env).ai_reasoning_enabled is expected

    def test_a_nonsense_value_still_raises(self, tmp_path, monkeypatch):
        """Only blank is treated as unset.

        Coercing everything to None would make `AI_REASONING_ENABLED=maybe` fail
        silently: thinking would be left at the provider default while the
        operator believed they had set something.
        """
        monkeypatch.delenv("AI_REASONING_ENABLED", raising=False)
        env = tmp_path / ".env"
        env.write_text("AI_REASONING_ENABLED=maybe", encoding="utf-8")

        with pytest.raises(ValidationError):
            Settings(_env_file=env)


class TestTheExampleDocumentsEveryKnob:
    def test_every_setting_appears_in_the_example(self):
        """A knob that is not in the example cannot be discovered or set.

        Checked against the model fields rather than a hand-kept list, so a new
        setting is caught here the moment it is added.
        """
        text = EXAMPLE.read_text(encoding="utf-8")
        # `host`/`port` and the legacy key aliases are not deployment knobs.
        skip = {"host", "port", "openrouter_api_key", "openai_api_key", "effective_ai_api_key", "effective_ai_url"}

        missing = [
            name.upper()
            for name in Settings.model_fields
            if name not in skip and name.upper() not in text
        ]

        assert not missing, f"undocumented in .env.example: {missing}"
