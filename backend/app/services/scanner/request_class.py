"""What a posting asks for, and whether the rules governing it permit it.

A pure function over facts on the face of the posting. It exists because the
verdict needs a stable input that is not a model's opinion: a fee to the
employer for a uniform and a fee to a personal GCash account are both "a fee",
and only the first is ordinary.

The rules, and the citations behind each one, are in
`docs/research/2026-10-21-verdict-grid-research.md` §4. The two that decide
most cases:

- DOLE DO 141-14 §35 forbids collecting a placement fee from a worker for
  local placement. DMW §56 allows exactly one overseas fee, payable only after
  a signed contract, so a fee to an agency before a contract is prohibited
  under either regime and this function does not need to know which one applies.
- RA 10173 §11(d) forbids collecting personal information that is excessive in
  relation to the purpose. The applicant packet is not excessive; a bank
  account, an e-wallet number or a one-time password is.

`IMPERSONATES_AUTHORITY` is deliberately not a request class. It is a claim the
posting makes about who it is, and establishment decides what to do with it.
"""

from __future__ import annotations

import re

from dataclasses import dataclass
from typing import Sequence

from app.services.scanner.channel_match import _domain_from_channel, _is_free_email


# Worst last: `_worst` returns the highest-ranked class present.
REQUEST_CLASSES = ("ordinary", "unclassified", "prohibited")
_CLASS_RANK = {name: index for index, name in enumerate(REQUEST_CLASSES)}


@dataclass(frozen=True)
class RequestFact:
    """One finding, reduced to the parts the classifier reads.

    Deliberately not the `Anomaly` schema: the classifier must be callable on a
    stored record, a test fixture, and a scan result without the caller having
    to construct a Pydantic model first.
    """

    code: str
    quote: str = ""
    fee_recipient: str = ""
    fee_timing: str = ""


# A fee, a purchase or a deposit. Decided by the recipient and the timing.
_FEE_CODES = frozenset({
    "FEE_MANDATORY", "FEE_CONDITIONAL", "PURCHASE_REQUIRED", "DEPOSIT_REQUIRED",
})

# No lawful reading of the request itself, whatever the employer turns out to be.
_PROHIBITED_CODES = frozenset({
    "ACCOUNT_CREDENTIALS", "PAYMENT_FORWARDING", "TASK_FOR_EARNING",
})

# The ordinary applicant packet. Named so a finding can say what is asked for
# without the reader losing anything by providing it.
_ORDINARY_CODES = frozenset({"APPLICATION_DOCUMENTS"})

# A claim about who the poster is. Establishment reads it; the request class
# does not, because the request itself may be entirely ordinary.
_ESTABLISHMENT_CODES = frozenset({"IMPERSONATES_AUTHORITY"})


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower()).strip(" .")


def _domains_in(text: str) -> list[str]:
    """Every hostname-like token in a quotation.

    The model writes the channel as it appears in the posting - an address, a
    link, or a bare hostname - so the tokens are split on whitespace and
    punctuation and each one is asked for a domain.
    """
    domains: list[str] = []
    for token in re.split(r"[\s,;|]+", str(text or "")):
        domain = _domain_from_channel(token)
        if domain:
            domains.append(domain)
    return domains


def _fee_class(fact: RequestFact) -> str:
    recipient = _normalise(fact.fee_recipient)
    timing = _normalise(fact.fee_timing)

    # A person, or an account the posting does not name as the employer's.
    # POEA Advisory 62 names remittance centres, GCash, 7/11 and PayPal.
    if any(word in recipient for word in ("individual", "personal", "third party")):
        return "prohibited"
    if "employer" in recipient:
        return "ordinary"
    if "agency" in recipient or "recruiter" in recipient:
        # DMW §56: the prescribed fee is payable after the contract is signed.
        # DO 141-14 §35: no fee at all for local placement. Either way, before
        # a contract the fee is prohibited.
        return "ordinary" if "contract" in timing else "prohibited"
    # The posting did not say who the money goes to. That is a question for the
    # reader, not a charge against the poster.
    return "unclassified"


def _documents_class(fact: RequestFact) -> str:
    domains = _domains_in(fact.quote)
    if not domains:
        # The code claims a third party, but names none. Nothing here can be
        # checked against the free-email list, and a charge cannot rest on what
        # the posting did not say.
        return "unclassified"
    if all(_is_free_email(domain) for domain in domains):
        # A free-provider address is the absence of a domain, not a third
        # party. The corpus measured the model using this code for Gmail.
        return "ordinary"
    return "prohibited"


def _class_for(fact: RequestFact) -> str:
    code = str(fact.code or "").strip().upper()

    if code in _PROHIBITED_CODES:
        return "prohibited"
    if code in _FEE_CODES:
        return _fee_class(fact)
    if code == "DOCUMENTS_VIA_THIRD_PARTY":
        return _documents_class(fact)
    if code in _ORDINARY_CODES:
        return "ordinary"
    if code in _ESTABLISHMENT_CODES:
        return "ordinary"

    # `OTHER`, an empty code, and anything outside the closed set. The escape
    # valve is a real finding whose shape the taxonomy does not name, so it
    # cannot be a charge - and it is not ordinary either. An unknown code is a
    # labelling miss, and clearing a posting because the model mistyped would
    # lose a real request silently.
    return "unclassified"


def classify_request(facts: Sequence[RequestFact], *, claimed_type: str = "") -> str:
    """The worst class present, in the order prohibited > unclassified > ordinary.

    `claimed_type` is the scan's `CLAIMED_TYPE` attribute. It is carried because
    the caller has it, and it is not read: the rules above do not need to know
    whether the work is local or overseas, because a fee to an agency before a
    contract is prohibited under both regimes.
    """
    worst = "ordinary"
    for fact in facts or ():
        candidate = _class_for(fact)
        if _CLASS_RANK[candidate] > _CLASS_RANK[worst]:
            worst = candidate
    return worst
