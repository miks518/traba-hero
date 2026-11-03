"""The authored statements and options for each assessment.

The panel never shows model prose. Every word is in code and looked up, like the
panel's own copy. The statement is rendered from structured facts off the record
— the amount, the fee's recipient and reason, what kind of documents — so the
panel never puts model prose in front of the reader.

The rule that catches me: a `green` statement must not say the posting asks for
nothing when it asks for something. A posting that asks for a 500 peso uniform
is green, and the sentence has to say so, because a false statement on the panel
is the one thing the libel guardrail cannot tolerate.

No statement contains an accusation and no statement contains a hedge — no
"likely", "appears", "suggests", "may", "might", "could". The same word ban
`clean_assessment_reason` applies, because the same reader-facing risk applies.
"""

from __future__ import annotations

import pytest

from app.services.scanner.establishment import Establishment
from app.services.scanner.assessment_copy import StatementFacts, statement, options


class TestGreenStatements:
    def test_a_green_statement_names_what_the_posting_does_ask(self):
        text = statement(
            "green",
            request_class="ordinary",
            establishment=Establishment("unknown"),
            facts=StatementFacts(amount="500", fee_reason="a uniform"),
        )
        assert "500" in text
        assert "uniform" in text
        assert "safe" not in text
        assert "legitimate" not in text
        assert "genuine" not in text

    def test_a_green_statement_never_says_the_employer_is_safe(self):
        text = statement(
            "green",
            request_class="ordinary",
            establishment=Establishment("unknown"),
            facts=StatementFacts(),
        )
        assert "safe" not in text
        assert "legitimate" not in text
        assert "genuine" not in text

    def test_a_green_statement_with_documents_names_them(self):
        text = statement(
            "green",
            request_class="ordinary",
            establishment=Establishment("supported"),
            facts=StatementFacts(documents="2x2 photo, NBI clearance"),
        )
        assert "2x2 photo" in text
        assert "NBI clearance" in text

    def test_a_green_statement_has_no_hedges(self):
        hedges = ["likely", "appears", "suggests", "may", "might", "could"]
        text = statement(
            "green",
            request_class="ordinary",
            establishment=Establishment("confirmed"),
            facts=StatementFacts(amount="1000", fee_reason="medical exam"),
        ).lower()
        for hedge in hedges:
            assert hedge not in text, f"green statement contains hedge: {hedge}"


class TestYellowStatements:
    def test_a_yellow_statement_names_the_fee_when_present(self):
        text = statement(
            "yellow",
            request_class="prohibited",
            establishment=Establishment("confirmed"),
            facts=StatementFacts(amount="1500", fee_reason="application fee", fee_recipient="employer"),
        )
        assert "1500" in text
        assert "application fee" in text
        assert "employer" in text

    def test_a_yellow_statement_at_a_confirmed_employer_says_so(self):
        """The rule, not the colour, carries the surprise: a verified employer
        whose posting still asks for something the rules prohibit.
        """
        text = statement(
            "yellow",
            request_class="prohibited",
            establishment=Establishment("confirmed"),
            facts=StatementFacts(amount="1500", fee_reason="application fee"),
        )
        assert "confirmed" in text.lower()

    def test_a_yellow_statement_at_a_supported_employer(self):
        text = statement(
            "yellow",
            request_class="unclassified",
            establishment=Establishment("supported"),
            facts=StatementFacts(),
        )
        assert "record" in text.lower()

    def test_a_yellow_statement_has_no_hedges(self):
        hedges = ["likely", "appears", "suggests", "may", "might", "could"]
        text = statement(
            "yellow",
            request_class="prohibited",
            establishment=Establishment("confirmed"),
            facts=StatementFacts(amount="500"),
        ).lower()
        for hedge in hedges:
            assert hedge not in text, f"yellow statement contains hedge: {hedge}"

    def test_a_yellow_statement_at_an_unknown_employer_names_the_gap(self):
        """The scam shape's sentence: what is asked for is stated, and what the
        record did not settle is stated, and neither is dressed as a verdict.
        """
        text = statement(
            "yellow",
            request_class="prohibited",
            establishment=Establishment("unknown"),
            facts=StatementFacts(amount="2000", fee_reason="processing fee", fee_recipient="agency"),
        )
        assert "2000" in text
        assert "processing fee" in text
        assert "agency" in text
        assert "Nothing in the record establishes" in text

    def test_a_yellow_statement_has_no_hedges_at_an_unknown_employer(self):
        hedges = ["likely", "appears", "suggests", "may", "might", "could"]
        text = statement(
            "yellow",
            request_class="prohibited",
            establishment=Establishment("unknown"),
            facts=StatementFacts(),
        ).lower()
        for hedge in hedges:
            assert hedge not in text, f"yellow statement contains hedge: {hedge}"


class TestRedStatements:
    def test_a_red_statement_names_the_impersonation(self):
        text = statement(
            "red",
            request_class="prohibited",
            establishment=Establishment("contradicted", reason="The domain is not the agency's."),
            facts=StatementFacts(),
            rule="establishment_contradicted",
        )
        assert "not from the employer it names" in text
        assert "contradicted" in text.lower() or "impersonat" in text.lower()

    def test_a_task_for_earning_red_does_not_claim_an_impersonation(self):
        """No employer is named, so nothing can have been impersonated.

        The red template says "The communication is not from the employer it
        names. This is a contradicted impersonation." That sentence is true for a
        contradicted channel and false for a DM: the posting names no employer at
        all, and inventing one so the sentence fits is the exact failure the
        libel guardrail exists to prevent. The rule name is what distinguishes
        them, so the rule is what the template reads.
        """
        text = statement(
            "red",
            request_class="prohibited",
            establishment=Establishment("unknown"),
            facts=StatementFacts(),
            rule="task_for_earning_at_unestablished_employer",
        )
        assert "impersonat" not in text.lower()
        assert "not from the employer" not in text.lower()
        assert "per task, order or referral" in text
        assert "nothing in the record establishes who would pay it" in text.lower()

    def test_a_finding_contradiction_red_does_not_claim_an_impersonation(self):
        """A source refuted a claim the posting made. That is not, on its own,
        a claim about who is asking, so the sentence must not say it is.
        """
        text = statement(
            "red",
            request_class="ordinary",
            establishment=Establishment("supported"),
            facts=StatementFacts(),
            rule="finding_contradicted_by_source",
        )
        assert "impersonat" not in text.lower()
        assert "not from the employer" not in text.lower()
        assert "a retrieved source states something different" in text.lower()

    def test_a_check_contradiction_red_does_not_claim_an_impersonation(self):
        text = statement(
            "red",
            request_class="ordinary",
            establishment=Establishment("supported"),
            facts=StatementFacts(),
            rule="check_contradicted_by_source",
        )
        assert "impersonat" not in text.lower()
        assert "not from the employer" not in text.lower()
        assert "a retrieved source contradicts" in text.lower()

    def test_every_red_rule_has_its_own_sentence(self):
        """One sentence per rule, because each rule is a different fact.

        A shared sentence would have to be vague enough to fit an impersonation,
        a refuted fee claim and an unestablished task offer at once - and the
        vague version is the one that gets defended to a panelist.
        """
        rules = (
            "establishment_contradicted",
            "task_for_earning_at_unestablished_employer",
            "finding_contradicted_by_source",
            "check_contradicted_by_source",
        )
        texts = {
            rule: statement(
                "red",
                request_class="prohibited",
                establishment=Establishment("contradicted", reason="r"),
                facts=StatementFacts(),
                rule=rule,
            )
            for rule in rules
        }
        assert len(set(texts.values())) == len(rules), (
            "two red rules share a sentence:\n"
            + "\n".join(f"  {r}: {t}" for r, t in texts.items())
        )

    def test_a_task_for_earning_red_has_no_hedges(self):
        hedges = ["likely", "appears", "suggests", "may", "might", "could"]
        text = statement(
            "red",
            request_class="prohibited",
            establishment=Establishment("unknown"),
            facts=StatementFacts(),
            rule="task_for_earning_at_unestablished_employer",
        ).lower()
        for hedge in hedges:
            assert hedge not in text, f"task-for-earning red contains hedge: {hedge}"

    def test_a_red_without_a_rule_keeps_the_contradiction_wording(self):
        """A stored scan and a caller that predates the rule field have none, and
        the contradiction wording is right for every red they can carry.
        """
        text = statement(
            "red",
            request_class="prohibited",
            establishment=Establishment("contradicted", reason="The domain is not the agency's."),
            facts=StatementFacts(),
        )
        assert "not from the employer it names" in text

    def test_a_red_statement_has_no_hedges(self):
        hedges = ["likely", "appears", "suggests", "may", "might", "could"]
        text = statement(
            "red",
            request_class="ordinary",
            establishment=Establishment("contradicted"),
            facts=StatementFacts(),
        ).lower()
        for hedge in hedges:
            assert hedge not in text, f"red statement contains hedge: {hedge}"


class TestOptions:
    def test_green_has_one_option(self):
        opts = options("green")
        assert len(opts) == 1
        # The option should be reader-facing, not an order, and must not claim
        # a clearance the grid never measured.
        assert any("continue" in o.lower() for o in opts)
        assert not any("proceed" in o.lower() for o in opts)

    def test_yellow_has_options(self):
        opts = options("yellow")
        assert len(opts) >= 1
        assert any("check" in o.lower() or "verify" in o.lower() or "confirm" in o.lower() for o in opts)

    def test_yellow_options_name_what_to_settle(self):
        opts = options("yellow")
        # Yellow options should tell the reader what to settle first
        assert any("what" in o.lower() or "who" in o.lower() or "confirm" in o.lower() for o in opts)

    def test_red_has_do_not_send_option(self):
        opts = options("red")
        assert len(opts) >= 1
        assert any("do not send" in o.lower() or "money" in o.lower() or "document" in o.lower() for o in opts)

    def test_unknown_assessment_returns_empty(self):
        opts = options("not_a_assessment")
        assert opts == ()
