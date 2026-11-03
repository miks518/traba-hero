"""The money-direction guard: a salary is not a fee.

Field test 2026-11-03: two of six postings whose only number was a salary came
back with a fee anomaly. The prompt has said the money rule twice — once in
`SYSTEM_PROMPT.md` and once in the fallback copy — and the model read it
anyway, which is the lesson `docs/decisions/search-retrieval.md` records about
the conclusion-word filter: a prompt sentence is not a control.

This suite pins the control. Three layers, each with its own test class:

- `quote_pays_the_applicant` — the reader of the span
- `scan_result._is_invented_fee` — the gate on the wire
- `request_class.classify_request` — the gate on the price
"""

import pytest

from app.services.money_direction import quote_pays_the_applicant
from app.services.scanner.request_class import RequestFact, classify_request


class TestTheReader:
    """A span is a payment request only when it tells the applicant to pay."""

    @pytest.mark.parametrize("quote", [
        "Salary P18,000-P22,000/month plus P1,500 allowance.",
        "Salary range: PHP 18,000 - PHP 22,000 per month",
        "Earn P30 per video liked.",
        "Monthly salary 25,000 plus 13th month pay.",
        "Pay rate: P500 per day",
        "Earn P25,000 per month, no experience needed.",
        "Sign up and earn P500 per referral.",
        "Send your resume and 2x2 photo to hr@acme.ph",
        "Salary: PHP 20,000. You can send your application to HR.",
        "",
    ])
    def test_pay_and_plain_application_text_is_not_a_payment_request(self, quote):
        assert quote_pays_the_applicant(quote) is False

    @pytest.mark.parametrize("quote", [
        "Pay P350 processing fee via GCash before your interview.",
        "Application fee of P100 must be settled first.",
        "We charge a fee of P500.",
        "Processing fee: P500",
        "Purchase your uniform before the start date.",
        "Buy your own tools.",
        "A deposit of P1,000 is required to hold your slot.",
        "Bring money for your medical examination.",
        "Send P200 to GCash 0917xxxxxxx.",
        "Send PHP 500 to 0917 123 4567 to reserve your slot.",
        "Salary negotiable. Kindly pay the P300 registration fee.",
        "Magbayad ng P500 para sa orientation.",
        "Bayad ng P500 ang uniform.",
    ])
    def test_a_request_to_pay_is_a_payment_request(self, quote):
        assert quote_pays_the_applicant(quote) is True

    @pytest.mark.parametrize("quote", [
        "We do not charge any fee.",
        "No placement fee is required.",
        "No application fee. Send your resume to hr@x.ph",
        "We never ask for payment.",
        "Free training. No fees at all.",
        "No processing fee of P500. Just bring your resume.",
        "Walang bayad ang application.",
    ])
    def test_a_span_that_says_there_is_no_charge_is_not_a_payment_request(self, quote):
        """The ordinary clean posting writes "no placement fee". A bare noun
        match on `fee` would read that as the exact inversion of what it says.
        """
        assert quote_pays_the_applicant(quote) is False

    def test_a_negation_clears_only_its_own_clause(self):
        """A posting can say "no fee" and demand a deposit in the next clause.
        Clearing the whole span would hide the deposit.
        """
        assert quote_pays_the_applicant(
            "No placement fee. A P1,000 deposit is required."
        ) is True
        assert quote_pays_the_applicant(
            "This is not a fee. Pay P500 for the uniform."
        ) is True


class TestTheWireGate:
    """`scan_result` drops a money finding whose quote shows pay, not a charge."""

    def test_a_salary_quoted_by_a_fee_finding_is_dropped(self):
        from app.services.scanner.scan_result import _anomalies

        out = _anomalies([{
            "flag": "Asks applicants to pay a fee",
            "reasoning": "The posting states a fee before starting work",
            "code": "FEE_MANDATORY",
            "quote": "Salary P18,000-P22,000 per month",
        }])
        assert out == []

    def test_a_real_fee_survives_whole(self):
        from app.services.scanner.scan_result import _anomalies

        out = _anomalies([{
            "flag": "Asks applicants to pay a processing fee",
            "reasoning": "The posting asks for P350 before the interview",
            "code": "FEE_MANDATORY",
            "quote": "Pay P350 processing fee via GCash before your interview.",
            "fee_reason": "processing",
        }])
        assert len(out) == 1
        assert out[0].code == "FEE_MANDATORY"
        assert out[0].quote.startswith("Pay P350")

    @pytest.mark.parametrize("code", ["FEE_MANDATORY", "FEE_CONDITIONAL",
                                      "PURCHASE_REQUIRED", "DEPOSIT_REQUIRED"])
    def test_every_money_code_is_guarded(self, code):
        from app.services.scanner.scan_result import _anomalies

        out = _anomalies([{
            "flag": "Asks applicants for money",
            "reasoning": "A salary is stated",
            "code": code,
            "quote": "Salary P20,000 per month",
        }])
        assert out == []

    def test_a_blank_quote_is_not_contradicted(self):
        """Absence is never a contradiction. A finding with no quote is a
        different defect with a different fix (`quote_is_clean` owns it), and
        this gate must not invent a reading of a span it was not given.
        """
        from app.services.scanner.scan_result import _is_invented_fee

        assert _is_invented_fee("FEE_MANDATORY", "") is False

    def test_a_non_money_code_is_not_guarded(self):
        from app.services.scanner.scan_result import _is_invented_fee

        assert _is_invented_fee("TASK_FOR_EARNING", "Salary P20,000") is False


class TestThePrice:
    """The classifier must not let an invented fee price a posting."""

    def test_an_invented_fee_does_not_price_prohibited(self):
        facts = [RequestFact(
            code="FEE_MANDATORY",
            fee_recipient="individual account",
            quote="Salary range PHP 18,000 to PHP 22,000 per month",
        )]
        assert classify_request(facts) == "ordinary"

    def test_a_real_fee_still_prices_prohibited(self):
        facts = [RequestFact(
            code="FEE_MANDATORY",
            fee_recipient="individual account",
            quote="Pay P350 processing fee via GCash",
        )]
        assert classify_request(facts) == "prohibited"


class TestTheScanResponse:
    """End to end: a clean posting with a salary does not read Caution."""

    def test_a_salary_with_an_invented_fee_is_a_clean_posting(self):
        from app.services.scanner.scan_result import _scan_response

        response = _scan_response({
            "valid": True,
            "anomalies": [
                {
                    "flag": "Asks applicants to pay a fee",
                    "reasoning": "A fee is mentioned",
                    "code": "FEE_MANDATORY",
                    "quote": "Salary P18,000-P22,000/month",
                }
            ],
            "attributes": {"FEE_RECIPIENT": "individual account"},
        }, "Acme Corp")

        assert response.anomalies == []
        assert response.request_class == "ordinary"
