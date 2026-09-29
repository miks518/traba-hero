"""Verification without a response schema.

A model with no endpoint OpenRouter can route a `response_format` request to
produces a 404, the client drops the schema, and the prompt has to carry the
output format on its own. Before this was asked of it, it did not: the prompt
named the fields but never said to return an object, and told the model to write
plain sentences. So a schema-less verify call returned prose, every parse came
back empty, and the panel showed the three category shells with no findings, no
Sources, no report, and no recommendation — silently, since the request itself
succeeded.

The load-bearing property is that the schema-less path produces the same four
outputs as the schema path, from one output shape rather than two.
"""

import json

from app.services.scanner.verification_prompt import VERIFY_SYSTEM_PROMPT
from app.services.scanner.offer_prompt import ANALYZE_OFFER_SYSTEM_PROMPT
from app.services.scanner.verification_flow import _read_verify_output
from app.services.scanner.offer_flow import _read_offer_output


# What a model without a schema produces once the prompt asks for JSON: a bare
# object, sometimes fenced, sometimes with a sentence around it. All three are
# shapes a real model emits, and `_parse_json` is documented to tolerate them.
UNSCHEMALED_JSON = json.dumps({
    "checks": [
        {
            "category": "Company Existence",
            "status": "green",
            "finding": "The results show a business operating as Acme Corporation at 12 Katipunan Ave.",
            "source_title": "Acme Corporation",
            "source_url": "https://example.ph/acme",
        },
        {
            "category": "Official Registration",
            "status": "yellow",
            "finding": "The provided results do not mention a registration for this company.",
            "source_title": "",
            "source_url": "",
        },
        {
            "category": "Reputation",
            "status": "yellow",
            "finding": "The provided results do not mention any report, complaint, or employee account.",
            "source_title": "",
            "source_url": "",
        },
    ],
    "evidence": [
        {
            "title": "Acme Corporation",
            "url": "https://example.ph/acme",
            "snippet": "Acme Corporation is a staffing firm based in Quezon City.",
        }
    ],
    "report": "The provided results show a business operating under the searched name. No registration is mentioned. This is based on public web search results only.",
    "recommendation": "The results showed a business by that name but no registration. Ask them to confirm the office address in writing before you visit.",
})


class TestThePromptAsksForJsonEvenWithoutASchema:
    def test_the_prompt_names_the_output_object(self):
        """Without a schema the prompt is the only thing specifying the shape.

        It already describes every field in prose, so a reader could infer the
        shape. Nothing tells the model to *return* it, and it is told to write
        plain sentences, so it writes plain sentences.
        """
        assert "JSON" in VERIFY_SYSTEM_PROMPT

    def test_the_prompt_names_all_four_keys(self):
        for key in ("checks", "evidence", "report", "recommendation"):
            assert key in VERIFY_SYSTEM_PROMPT, key


class TestUnschemaedOutputIsRead:
    def _read(self, text):
        return _read_verify_output(text)

    def test_a_bare_object_yields_every_category(self):
        items, _, _, used_json, _ = self._read(UNSCHEMALED_JSON)

        assert used_json is True
        assert [i.label for i in items] == [
            "Company Existence", "Official Registration", "Reputation",
        ]

    def test_a_fenced_object_is_read(self):
        fenced = f"Here is the result:\n```json\n{UNSCHEMALED_JSON}\n```"
        items, report, recommendation, used_json, evidence = self._read(fenced)

        assert used_json is True
        assert len(items) == 3
        assert report
        assert recommendation
        assert evidence[0]["url"] == "https://example.ph/acme"

    def test_sources_survive_without_a_schema(self):
        """Evidence was hardcoded to an empty list on the text path.

        That is the defect this covers: a reader gets the findings but no way to
        check them, and the panel renders the Sources section from this list, so
        an empty one removes the section entirely.
        """
        _, _, _, _, evidence = self._read(UNSCHEMALED_JSON)

        assert evidence == [
            {
                "title": "Acme Corporation",
                "url": "https://example.ph/acme",
                "snippet": "Acme Corporation is a staffing firm based in Quezon City.",
            }
        ]

    def test_the_report_and_recommendation_survive(self):
        _, report, recommendation, _, _ = self._read(UNSCHEMALED_JSON)

        assert "public web search results only" in report
        assert "confirm the office address" in recommendation

    def test_the_schema_and_no_schema_paths_agree(self):
        """One output shape, not two.

        The same JSON must read identically whether it arrived under a schema or
        not, so the panel cannot show a different panel depending on which
        endpoint the provider happened to route to.
        """
        from_schema = self._read(UNSCHEMALED_JSON)
        without_schema = self._read(f"```json\n{UNSCHEMALED_JSON}\n```")

        assert from_schema == without_schema


class TestTheOfferPathSharesTheDefect:
    """`/api/analyze-offer` sends a schema for the same reason verify does.

    A model with no schema-capable endpoint drops the schema here too, and this
    prompt had the same gap: field rules but no instruction to return an object,
    plus a "plain sentences only" rule that pushed the model the other way. Its
    fallback parser reads a labeled format the prompt also stopped asking for.
    """

    def test_the_offer_prompt_asks_for_json(self):
        assert "JSON" in ANALYZE_OFFER_SYSTEM_PROMPT

    def test_the_offer_prompt_names_every_key(self):
        for key in ("kind", "verdict", "what_it_asks", "what_it_offers", "what_to_check", "is_offer"):
            assert key in ANALYZE_OFFER_SYSTEM_PROMPT, key

    def test_a_fenced_offer_object_is_still_read(self):
        payload = json.dumps({
            "kind": "Recruitment pitch",
            "verdict": "The offer asks for a processing fee before any interview.",
            "what_it_asks": "A 500 peso processing fee sent by GCash before an interview.",
            "what_it_offers": "A work-from-home office assistant role.",
            "what_to_check": "The employer's registered business name.",
            "is_offer": True,
        })
        parsed = _read_offer_output(f"```json\n{payload}\n```")

        assert parsed is not None
        assert parsed["kind"] == "Recruitment pitch"
        assert parsed["is_offer"] is True
