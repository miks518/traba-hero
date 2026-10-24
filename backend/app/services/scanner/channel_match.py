"""Channel Match: the model reports facts, this module assigns the severity.

The verification model used to decide the Channel Match status itself, and the
prompt told it that *any* different channel was red. That is wrong for the
ordinary Philippine case: a real employer whose contact is
`name.company@gmail.com` while its own site is `company.com.ph` produced a red
card and, because the same model also emitted the overall level, "Do not
proceed" from one weak observation. The model is good at copying what a posting
names and what the company's own pages use. It is not the right place to decide
what that difference means.

So the wire now carries `channel_match` facts: the printed channels, the
official channels, whether the posting claims to be government, and a factual
sentence. The rules below turn those facts into a status. They are deliberately
narrow:

* A free-provider email at an otherwise matching company is informational. It is
  the ordinary case, not a contradiction.
* A government claim with a printed channel outside `.gov.ph` is a contradiction.
* A printed domain that imitates the official one is a contradiction.
* A non-matching channel plus a separate finding (a fee, a chat-only interview,
  documents sent to a third party) is a contradiction, because the combination is
  the pattern, not the channel alone.
* Anything else is yellow. "The results do not confirm this channel" is not the
  same claim as "the results contradict this channel", and only the second is red.

The status vocabulary is unchanged (`green` / `yellow` / `red`), so the panel and
`risk_calculator` need no new rendering. The `escalation` field on
`VerificationItem` is the code's own reason, and the final verdict reads it to
give a strong impersonation finding a floor that one weak finding cannot reach.
See `docs/decisions/channel-match-severity.md`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from app.models.schemas import VerificationItem

# Free mailbox providers, including the ones common in Philippine postings.
# A free address is not evidence of impersonation: a small employer may have no
# domain at all, and the local part often carries the company name precisely
# because that is the only identifier Gmail gives it.
FREE_EMAIL_DOMAINS = frozenset({
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "yahoo.com.ph",
    "ymail.com",
    "rocketmail.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "msn.com",
    "icloud.com",
    "me.com",
    "mac.com",
    "aol.com",
    "protonmail.com",
    "proton.me",
    "gmx.com",
    "mail.com",
    "zoho.com",
    "yandex.com",
})

# A government office's own domain ends here. The leading dot matters:
# `notgov.ph` is not a government domain, and neither is `gov.ph.example.com`.
_GOVERNMENT_SUFFIX = ".gov.ph"

# The escalations that are a claim the posting makes about itself, and therefore
# need no retrieved source. A government office using a domain outside `.gov.ph`
# is visible in the posting alone: the posting claimed to be the office, and the
# posting supplied the domain. Everything else - a lookalike of the official
# domain, an unconfirmed channel, a free email - compares the posting against
# something retrieved, so it cannot stand without that source.
SOURCE_INDEPENDENT_ESCALATIONS = frozenset({"government"})

# The second-level suffixes the Philippines uses. Enough to find the brand label
# in `company.com.ph`; a full public-suffix list is unnecessary because every
# domain this check compares is one the verification model reported for a
# Philippine employer.
_PH_SUFFIXES = frozenset({
    "com.ph", "gov.ph", "org.ph", "net.ph", "edu.ph", "mil.ph",
})

# Words that cannot appear in a factual finding we reuse. The prompt already
# bans them; this is the code-side check because the finding is displayed as the
# explanation on a card the reader may act on. A rejected sentence degrades to
# the code-authored explanation, which is complete on its own.
_FINDING_BANNED = (
    "scam", "scammer", "fraud", "fraudulent", "fake", "falsify", "falsified",
    "suspicious", "illegitimate", "criminal", "legitimate", "genuine",
    "trustworthy", "verified", "safe", "authorized",
    "likely", "probably", "seemingly", "appears to", "appears that",
    "suggests that", "suggests the", "might be", "may be", "could indicate",
    "potentially", "always", "never", "definitely", "guaranteed", "100%",
)

NO_DATA_EXPLANATION = (
    "The results do not name a contact channel for this employer, so the "
    "posting's channel could not be compared."
)


@dataclass(frozen=True)
class ChannelFacts:
    """What the verify model reported about the posting's and employer's channels."""

    printed_channels: tuple[str, ...] = ()
    official_channels: tuple[str, ...] = ()
    government_claim: bool = False
    finding: str = ""
    source_title: str = ""
    source_url: str = ""


@dataclass(frozen=True)
class ChannelAssessment:
    """The code's status and the rule that produced it."""

    status: str
    explanation: str
    escalation: str
    strong: bool = False


def read_channel_facts(raw: object) -> ChannelFacts | None:
    """Read the `channel_match` object, tolerating a missing or malformed one.

    A response recorded before this field existed has no object, and a
    schema-less model may answer with a different shape. `None` means "no facts
    were reported", which is different from an object with empty lists: the
    latter says the model looked and found no channel, the former says the field
    was not part of the output at all. Both end at the same yellow card, but the
    distinction is useful in the log.
    """
    if not isinstance(raw, dict):
        return None

    return ChannelFacts(
        printed_channels=_read_channels(raw.get("printed_channels")),
        official_channels=_read_channels(raw.get("official_channels")),
        government_claim=_read_bool(raw.get("government_claim")),
        finding=str(raw.get("finding") or "").strip(),
        source_title=str(raw.get("source_title") or "").strip(),
        source_url=str(raw.get("source_url") or "").strip(),
    )


def has_channel_content(facts: ChannelFacts | None) -> bool:
    """Whether there is anything for the rules to compare."""
    return bool(
        facts
        and (
            facts.printed_channels
            or facts.official_channels
            or facts.government_claim
        )
    )


def assess_channel_match(facts: ChannelFacts) -> ChannelAssessment:
    """Assign the Channel Match status from the facts alone.

    Nothing about what the posting asks for is read here. The combination rule
    — a channel the employer does not control, plus a request the rules
    prohibit — needs the request class, which the flow holds and this stage
    does not. `apply_channel_rules` finishes the decision for that reason.
    """
    printed = facts.printed_channels
    official = facts.official_channels
    printed_domains = tuple(_domain_from_channel(c) for c in printed)
    official_domains = tuple(_domain_from_channel(c) for c in official)

    is_government = facts.government_claim or any(
        _is_government_domain(d) for d in official_domains if d
    )
    non_government = tuple(
        channel
        for channel in printed
        if (domain := _domain_from_channel(channel))
        and not _is_government_domain(domain)
    )

    # A government office using a domain outside `.gov.ph` is the strongest
    # signal available, and it needs no retrieved source to see: the posting made
    # the claim and the posting supplied the domain. Lookalikes need the official
    # domain, which is bound to a retrieved result before this runs.
    if is_government and non_government:
        return ChannelAssessment(
            status="red",
            explanation=_government_explanation(facts, is_government, non_government),
            escalation="government",
            strong=True,
        )

    lookalike = _first_lookalike(printed_domains, official_domains)
    if lookalike:
        printed_domain, official_domain = lookalike
        return ChannelAssessment(
            status="red",
            explanation=(
                f"The posting gives {_quote(printed_domain)} as a contact, while "
                f"the company's own results use {_quote(official_domain)}. The two "
                "domains are different."
            ),
            escalation="lookalike",
            strong=True,
        )

    free = tuple(
        channel
        for channel in printed
        if (domain := _domain_from_channel(channel)) and _is_free_email(domain)
    )
    if free:
        return ChannelAssessment(
            status="yellow",
            explanation=_free_email_explanation(facts, free[0], official_domains),
            escalation="free_email",
        )

    # Every printed channel that is a domain either matches the official channel
    # or is unknown. A raw match catches a phone number or a messaging handle that
    # has no domain to compare.
    domains_printed = tuple(d for d in printed_domains if d)
    if domains_printed:
        unmatched = tuple(
            channel
            for channel in printed
            if (domain := _domain_from_channel(channel))
            and not any(_matches_domain(domain, o) for o in official_domains if o)
        )
        if unmatched:
            return ChannelAssessment(
                status="yellow",
                explanation=_unconfirmed_explanation(
                    facts, unmatched[0], official_domains
                ),
                escalation="unconfirmed",
            )
        # All domain channels match. A second, non-domain channel that does not
        # match is still unknown, so it is not green.
        if _every_channel_matches(printed, official):
            return ChannelAssessment(
                status="green",
                explanation=_match_explanation(facts, official_domains),
                escalation="match",
            )
        return ChannelAssessment(
            status="yellow",
            explanation=_unconfirmed_explanation(facts, "", official_domains),
            escalation="unconfirmed",
        )

    # No domains at all: a phone number, a messaging handle, or a meeting place.
    if _every_channel_matches(printed, official) and printed:
        return ChannelAssessment(
            status="green",
            explanation=_match_explanation(facts, ()),
            escalation="match",
        )

    return ChannelAssessment(
        status="yellow",
        explanation=NO_DATA_EXPLANATION,
        escalation="no_data",
    )


def apply_channel_rules(
    items: list[VerificationItem],
    request_class: str,
    expected: set[str],
) -> list[VerificationItem]:
    """Finish the Channel Match decision with what the posting asked for.

    The parser can only see the model's channel facts; the request class is
    decided by `request_class.classify_request` from the posting's findings and
    attributes. This step is where the two meet, so it is where a channel the
    employer does not control becomes part of a pattern — and only when the
    request is one the rules prohibit. A free email plus the ordinary applicant
    packet is what Philippine hiring looks like; the corpus measured the old
    rule pushing two legitimate postings to "Proceed with caution" (25 + 12 =
    37 both times).

    It also removes a Channel Match card the posting made no claim for, and
    refuses to let an old response's model-assigned status stand: a Channel
    Match item with no `escalation` came from before the facts split, and its
    status is the model's, not the code's.
    """
    channel = next((item for item in items if item.label == "Channel Match"), None)

    if "Channel Match" not in expected:
        return [item for item in items if item.label != "Channel Match"]

    if channel is None:
        if not items:
            # Let the flow's failsafe handle a response that carried nothing at
            # all. A yellow "could not compare" card is not a usable check, and
            # adding one here would suppress the notice that says the model's
            # answer could not be read.
            return items
        items.append(VerificationItem(
            label="Channel Match",
            status="yellow",
            explanation=NO_DATA_EXPLANATION,
            escalation="no_data",
        ))
        return items

    if not channel.escalation:
        # A response from before the facts split, or a schema-less answer that
        # still put Channel Match in `checks`. The model's status is not used.
        channel.status = "yellow"
        channel.explanation = NO_DATA_EXPLANATION
        channel.source_title = ""
        channel.source_url = ""
        channel.escalation = "no_data"
        return items

    if channel.escalation in ("free_email", "unconfirmed"):
        if request_class == "prohibited":
            channel.status = "red"
            channel.escalation = f"{channel.escalation}_with_findings"
            channel.explanation = (
                f"{channel.explanation} The posting also asks for something the "
                "rules prohibit."
            )

    return items


def _read_channels(raw: object) -> tuple[str, ...]:
    if isinstance(raw, str):
        text = raw.strip()
        return (text,) if text else ()
    if not isinstance(raw, list):
        return ()
    values = []
    for value in raw:
        text = str(value or "").strip()
        if text:
            values.append(text)
    return tuple(values)


def _read_bool(raw: object) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in {"true", "yes", "1"}
    return False


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _domain_from_channel(value: str) -> str:
    """The hostname in an email address or URL, else empty.

    A phone number, a meeting place, and a messaging handle all return empty:
    they have no domain to compare, and pretending they do is how a different
    meeting spot becomes a contradiction.
    """
    text = _normalise(value)
    if not text:
        return ""
    if text.startswith("mailto:"):
        text = text[len("mailto:"):]
    if "@" in text:
        text = text.rsplit("@", 1)[1]
    else:
        text = re.sub(r"^[a-z][a-z0-9+.-]*://", "", text)
        text = text.split("/", 1)[0]
        text = text.split("?", 1)[0]
        text = text.split("#", 1)[0]
    text = text.strip().strip(".,;:()[]<>\"'")
    if text.startswith("www."):
        text = text[len("www."):]
    if not text or " " in text or "." not in text:
        return ""
    if not re.fullmatch(r"[a-z0-9.-]+", text):
        return ""
    return text.strip(".")


def _is_free_email(domain: str) -> bool:
    return any(
        domain == provider or domain.endswith("." + provider)
        for provider in FREE_EMAIL_DOMAINS
    )


def _is_government_domain(domain: str) -> bool:
    return domain == "gov.ph" or domain.endswith(_GOVERNMENT_SUFFIX)


def _matches_domain(printed: str, official: str) -> bool:
    if not printed or not official:
        return False
    return (
        printed == official
        or printed.endswith("." + official)
        or official.endswith("." + printed)
    )


def _matches_raw(printed: str, official: str) -> bool:
    if _normalise(printed) == _normalise(official):
        return True
    return _matches_domain(
        _domain_from_channel(printed), _domain_from_channel(official)
    )


def _every_channel_matches(printed: tuple[str, ...], official: tuple[str, ...]) -> bool:
    if not printed or not official:
        return False
    for channel in printed:
        if not any(_matches_raw(channel, candidate) for candidate in official):
            return False
    return True


def _brand_label(domain: str) -> str:
    labels = [label for label in domain.split(".") if label]
    if not labels:
        return ""
    if len(labels) >= 3 and ".".join(labels[-2:]) in _PH_SUFFIXES:
        return labels[-3]
    if len(labels) >= 2:
        return labels[-2]
    return labels[0]


def _tokens(label: str) -> tuple[str, ...]:
    return tuple(token for token in re.split(r"[^a-z0-9]+", label.lower()) if token)


def _edit_distance(a: str, b: str) -> int:
    """Damerau-Levenshtein distance, capped by the strings' lengths.

    The transposition case matters for the typo this check exists to catch:
    `knollrigdes` is one transposition from `knollridges`, and a plain
    Levenshtein counts it as two.
    """
    if a == b:
        return 0
    previous_previous: list[int] = []
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, 1):
        current = [i]
        for j, char_b in enumerate(b, 1):
            cost = 0 if char_a == char_b else 1
            current.append(min(
                current[j - 1] + 1,
                previous[j] + 1,
                previous[j - 1] + cost,
            ))
            if (
                i > 1
                and j > 1
                and char_a == b[j - 2]
                and a[i - 2] == char_b
            ):
                current[j] = min(current[j], previous_previous[j - 2] + 1)
        previous_previous, previous = previous, current
    return previous[-1]


def _is_lookalike(printed: str, official: str) -> bool:
    if not printed or not official or _matches_domain(printed, official):
        return False
    printed_brand = _brand_label(printed)
    official_brand = _brand_label(official)
    if not printed_brand or not official_brand:
        return False
    if printed_brand == official_brand:
        return True
    # A brand followed by a suffix is the same impersonation pattern as a typo:
    # `companycareers.com` and `company-ph.com` both use the company's own name.
    # Three characters is enough for a real acronym (`paf`), and the official
    # domain is known, so the prefix is not a guess about the whole internet.
    if len(official_brand) >= 3 and printed_brand.startswith(official_brand):
        return True
    # A separated token can also be the brand: `jobs-company.com` has `company`
    # as a token, while the label does not start with it.
    if official_brand in _tokens(printed_brand):
        return True
    for printed_token in _tokens(printed_brand):
        for official_token in _tokens(official_brand):
            if len(printed_token) < 4 or len(official_token) < 4:
                continue
            if printed_token == official_token:
                return True
            if _edit_distance(printed_token, official_token) <= 1:
                return True
    return False


def _first_lookalike(
    printed: tuple[str, ...], official: tuple[str, ...]
) -> tuple[str, str] | None:
    for printed_domain in printed:
        for official_domain in official:
            if _is_lookalike(printed_domain, official_domain):
                return printed_domain, official_domain
    return None


def _clean_finding(facts: ChannelFacts) -> str:
    text = facts.finding.strip()
    if not text:
        return ""
    lowered = text.lower()
    if any(word in lowered for word in _FINDING_BANNED):
        return ""
    return text


def _quote(value: str) -> str:
    return f'"{value}"' if value else "the channel"


def _join(values: tuple[str, ...]) -> str:
    unique = []
    for value in values:
        if value and value not in unique:
            unique.append(value)
    if not unique:
        return ""
    if len(unique) == 1:
        return _quote(unique[0])
    return ", ".join(_quote(v) for v in unique[:-1]) + f" and {_quote(unique[-1])}"


def _free_email_explanation(
    facts: ChannelFacts, channel: str, official_domains: tuple[str, ...]
) -> str:
    parts = []
    finding = _clean_finding(facts)
    if finding:
        parts.append(finding)
    official = _join(official_domains)
    if official:
        parts.append(
            f"The posting uses a free email address ({_quote(channel)}), while the "
            f"company's own results use {official}."
        )
    else:
        parts.append(
            f"The posting uses a free email address ({_quote(channel)})."
        )
    parts.append(
        "A free email address is ordinary in Philippine job postings, so this is "
        "not a contradiction by itself."
    )
    return " ".join(parts)


def _government_explanation(
    facts: ChannelFacts, claimed: bool, non_government: tuple[str, ...]
) -> str:
    printed = _join(non_government or facts.printed_channels)
    official = _join(facts.official_channels)
    if claimed and facts.government_claim:
        first = (
            f"The posting presents the employer as a government office and gives "
            f"{printed} as a contact."
        )
    else:
        first = (
            f"The posting gives {printed} as a contact while the employer's own "
            "results use a government domain."
        )
    if official:
        return (
            f"{first} That is outside the .gov.ph domain the agency's own results "
            f"use ({official})."
        )
    return f"{first} That is outside the .gov.ph domain."


def _unconfirmed_explanation(
    facts: ChannelFacts, channel: str, official_domains: tuple[str, ...]
) -> str:
    printed = _quote(channel) if channel else _join(facts.printed_channels)
    official = _join(official_domains)
    if official:
        return (
            f"The posting gives {printed} as a contact. The results show "
            f"{official} for this employer, not that channel."
        )
    return f"The posting gives {printed} as a contact, and the results do not show that channel for this employer."


def _match_explanation(
    facts: ChannelFacts, official_domains: tuple[str, ...]
) -> str:
    finding = _clean_finding(facts)
    if finding:
        return finding
    official = _join(official_domains)
    if official:
        return f"The posting's contact channel matches the one the employer's own results use ({official})."
    return "The posting's contact channel matches the one the employer's own results use."


def with_official_only_if_retrieved(facts: ChannelFacts, retrieved: bool) -> ChannelFacts:
    """Drop official channels the search did not return.

    The official side of the comparison is a claim about the employer, and the
    standing rule is that a claim nobody could confirm is yellow. A model can
    copy a domain from the posting itself and call it the employer's; without a
    retrieved result behind it, the comparison has no anchor and the status must
    not become red. The flow calls this after binding `source_url`.
    """
    if retrieved and facts.source_url:
        return facts
    if not facts.official_channels:
        return facts
    return replace(facts, official_channels=(), source_title="", source_url="")
