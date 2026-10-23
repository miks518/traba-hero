"""What a posting asks for, classified against the rules that govern it.

The classifier is a pure function over facts on the face of the posting. It
exists because the verdict needs a stable input that is not a model's opinion:
a fee to the employer for a uniform and a fee to a personal GCash account are
both "a fee", and only the first is ordinary.

The rules and their citations are in
`docs/research/2026-10-21-verdict-grid-research.md` §4.
"""

from app.services.scanner.request_class import (
    REQUEST_CLASSES,
    RequestFact,
    classify_request,
)


def test_the_classes_are_a_closed_set():
    assert REQUEST_CLASSES == ("ordinary", "unclassified", "prohibited")


def test_a_posting_with_no_findings_is_ordinary():
    assert classify_request([]) == "ordinary"


def test_a_free_email_with_an_ordinary_packet_is_ordinary():
    """The corpus's worst false positive. A 2x2 photo and an NBI clearance at a
    Gmail address is what a small Philippine employer's hiring looks like.
    """
    facts = [RequestFact(code="APPLICATION_DOCUMENTS", quote="2x2 picture, NBI clearance")]
    assert classify_request(facts) == "ordinary"


def test_account_credentials_before_hiring_are_prohibited():
    """No employer needs a bank account or an OTP to consider an application,
    and RA 10173 s11(d) forbids collecting more personal information than the
    purpose requires.
    """
    facts = [RequestFact(code="ACCOUNT_CREDENTIALS")]
    assert classify_request(facts) == "prohibited"


def test_a_fee_to_an_agency_before_hiring_is_prohibited():
    """DOLE DO 141-14 s35: no fee may be collected from a worker for local
    placement. DMW s56 allows the prescribed overseas fee only after a signed
    contract, so pre-contract is prohibited either way.
    """
    facts = [RequestFact(code="FEE_MANDATORY", fee_recipient="agency", fee_timing="before hiring")]
    assert classify_request(facts, claimed_type="recruitment agency") == "prohibited"


def test_a_fee_to_the_employer_for_a_uniform_is_ordinary():
    """DO 141-14 governs agencies, not employers. A uniform or a medical exam
    charged by the employer is ordinary practice, and the reason is stated.
    """
    facts = [RequestFact(code="FEE_MANDATORY", fee_recipient="employer",
                         fee_timing="before hiring", quote="uniform")]
    assert classify_request(facts) == "ordinary"


def test_a_fee_to_an_individual_account_is_prohibited():
    """POEA Advisory 62 names remittance centres, GCash, 7/11 and PayPal: a
    fee paid to a person rather than an institution is the pattern.
    """
    facts = [RequestFact(code="FEE_MANDATORY", fee_recipient="individual account")]
    assert classify_request(facts) == "prohibited"


def test_a_fee_with_no_stated_recipient_cannot_be_classified():
    """The absence of a fact is a question, not a charge. The panel asks what
    the reader knows rather than asserting what the posting did not say.
    """
    facts = [RequestFact(code="FEE_MANDATORY")]
    assert classify_request(facts) == "unclassified"


def test_a_fee_to_an_agency_after_a_signed_contract_is_ordinary():
    """DMW s56 permits exactly one placement fee, and only after the contract
    is signed. The timing is what separates it from the prohibited case.
    """
    facts = [RequestFact(code="FEE_MANDATORY", fee_recipient="agency", fee_timing="after a contract")]
    assert classify_request(facts, claimed_type="recruitment agency") == "ordinary"


def test_a_conditional_fee_follows_the_same_rules_as_a_mandatory_one():
    """Refundability does not make a fee lawful. A "refundable" seminar fee
    paid to an agency before a contract is the same prohibited request.
    """
    facts = [RequestFact(code="FEE_CONDITIONAL", fee_recipient="agency", fee_timing="before hiring")]
    assert classify_request(facts) == "prohibited"


def test_a_purchase_required_from_an_individual_is_prohibited():
    facts = [RequestFact(code="PURCHASE_REQUIRED", fee_recipient="individual account")]
    assert classify_request(facts) == "prohibited"


def test_documents_via_a_free_provider_are_ordinary():
    """The corpus measured the model using this code for a Gmail address. A
    free-provider address is the absence of a domain, not a third party.
    """
    facts = [RequestFact(code="DOCUMENTS_VIA_THIRD_PARTY", quote="recruitment4@gmail.com")]
    assert classify_request(facts) == "ordinary"


def test_documents_via_a_named_domain_are_prohibited():
    facts = [RequestFact(code="DOCUMENTS_VIA_THIRD_PARTY", quote="send to forms.hiredocs.net")]
    assert classify_request(facts) == "prohibited"


def test_documents_with_no_named_domain_cannot_be_classified():
    """A finding that names no domain cannot be checked against the free-email
    list, and a charge cannot rest on what the posting did not say.
    """
    facts = [RequestFact(code="DOCUMENTS_VIA_THIRD_PARTY", quote="send your documents")]
    assert classify_request(facts) == "unclassified"


def test_task_for_earning_is_prohibited():
    assert classify_request([RequestFact(code="TASK_FOR_EARNING")]) == "prohibited"


def test_payment_forwarding_is_prohibited():
    assert classify_request([RequestFact(code="PAYMENT_FORWARDING")]) == "prohibited"


def test_impersonation_is_not_a_request_class():
    """It is an establishment signal, and Part 4 reads it. A posting that
    impersonates an agency but asks for nothing unusual has asked for nothing
    unusual.
    """
    assert classify_request([RequestFact(code="IMPERSONATES_AUTHORITY")]) == "ordinary"


def test_other_cannot_be_a_charge():
    """The escape valve says a finding exists whose shape the taxonomy does not
    name. A charge is defined by the shape, so it cannot be made here.
    """
    assert classify_request([RequestFact(code="OTHER")]) == "unclassified"


def test_the_worst_class_present_wins():
    facts = [
        RequestFact(code="APPLICATION_DOCUMENTS"),
        RequestFact(code="FEE_MANDATORY", fee_recipient="agency", fee_timing="before hiring"),
        RequestFact(code="OTHER"),
    ]
    assert classify_request(facts) == "prohibited"


def test_an_unknown_code_is_not_silently_ordinary():
    """A code the set does not know is a labelling miss. Treating it as
    ordinary would let a real request disappear because the model mistyped.
    """
    assert classify_request([RequestFact(code="FEE_MANDATROY")]) == "unclassified"


# --- the scan builds the facts --------------------------------------------


def test_the_scan_facts_pair_each_finding_with_the_postings_fee_facts():
    """The recipient and timing are posting-level attributes, so they are
    attached to every finding rather than read from the anomaly. A posting that
    names one recipient has named it for its fees.
    """
    from app.services.scanner.request_class import facts_from_scan

    facts = facts_from_scan(
        [{"code": "FEE_MANDATORY"}, {"code": "APPLICATION_DOCUMENTS"}],
        {"FEE_RECIPIENT": "agency", "FEE_TIMING": "before hiring"},
    )

    assert facts[0].code == "FEE_MANDATORY"
    assert facts[0].fee_recipient == "agency"
    assert facts[0].fee_timing == "before hiring"
    assert facts[1].code == "APPLICATION_DOCUMENTS"


def test_a_scan_carries_its_request_class():
    """The scan reads the posting, so it is the stage that knows what the
    posting asks for. The verify stage carries the same value rather than
    recomputing it from a different list.
    """
    from app.services.scanner.scan_result import _scan_response

    response = _scan_response(
        {
            "valid": True,
            "anomalies": [
                {"flag": "Asks for a fee", "reasoning": "A fee", "severity": "high",
                 "code": "FEE_MANDATORY"},
            ],
            "attributes": {"COMPANY": "Acme"},
        },
        "Acme",
    )

    assert response.request_class == "unclassified"
