"""Adaptive verification search: the pure half.

The planner and the resolver are pure functions of the scan's own fields and
Round 1's results. That is the point of the design — **query planning is code, so
it is deterministic and testable offline** — and it is why this module performs no
I/O at all.

`plan_followups` chooses questions. **It never decides anything.** No value here
sets a status; the verify prompt remains the only thing that makes a claim about
an employer. A wrong entity-domain produces a wrong query, not a wrong assessment.

Design: `docs/superpowers/specs/2026-10-18-adaptive-verification-search.md`
"""

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from app.models.schemas import MAX_VERIFY_QUERY_CHARS
from app.services.search import registrable_domain

log = logging.getLogger("trabahero")

# The ceiling from the proposal, enforced here rather than at the call site.
# The anchor query is spent separately, so this many follow-ups keeps a
# verification at three credits — the same ceiling as today.
MAX_FOLLOWUPS = 2

# The rule the scan prompt states in prose, enforced here so a model cannot
# produce a query around it.
#
# A query carrying an accusation returns pages chosen *because* they contain that
# word, which then read as confirmation of an accusation the query invented. The
# same sentence is in `SCAN_FIELD_RULES`; this is the control behind it.
_BANNED_QUERY_TERMS = (
    "scam", "scammer", "fraud", "fraudulent", "fake", "suspicious", "legitimate",
)

# Domains that host other people's pages. Taking one as "the employer's domain"
# produces a scoped query about a job board.
_AGGREGATOR_DOMAINS = frozenset({
    "linkedin.com", "facebook.com", "fb.com", "instagram.com", "twitter.com",
    "x.com", "tiktok.com", "youtube.com", "reddit.com", "t.me", "wa.me",
    "whatsapp.com", "glassdoor.com", "indeed.com", "monster.com",
    "jobstreet.com", "jobstreet.com.ph", "jobs.ph", "hire.com.ph",
    "ziprecruiter.com", "jobvite.com", "bamboohr.com", "workable.com",
    "news.google.com", "medium.com", "wikipedia.org", "youtube.com",
    # URL shorteners. A shortener redirects to somewhere else, so its own page
    # never describes the employer, and querying one spends a credit on the
    # redirect service's homepage. A posting that applies through bit.ly is
    # common, which is exactly why it must not read as the employer's domain.
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "is.gd", "cutt.ly", "rebrand.ly",
    "shorturl.at", "rb.gy", "ow.ly", "buff.ly", "lnkd.in",
})

# The channel types the scan prompt allows, of which these three carry no host
# to imitate. The type is free signal - the typed format exists so that nothing
# has to be split on a separator - and it is what says a street address is a
# place rather than a domain.
_HOSTLESS_CHANNEL_TYPES = frozenset({"phone", "messaging", "address"})

# Where many Philippine employers hire, and what is therefore ordinary.
_FREE_EMAIL_DOMAINS = frozenset({
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.com.ph", "ymail.com",
    "hotmail.com", "outlook.com", "live.com", "msn.com", "aol.com",
    "icloud.com", "me.com", "protonmail.com", "proton.me", "zoho.com",
    "mail.ru", "gmx.com", "gmx.de", "yandex.com", "web.de", "hey.com",
})

_LEGAL_SUFFIXES = frozenset({
    "inc", "incorporated", "corp", "corporation", "co", "company", "ltd",
    "limited", "llc", "plc", "gmbh", "sa", "sdn", "bhd", "pty", "the",
})

# A name is "the same" when at least this much of what the poster printed appears
# in the name the results use.
#
# Measured against the PRINTED name's tokens, not a symmetric ratio: the question
# is how much of the poster's claim survives, so a longer official name cannot
# make a mangled one look matched. "Commission for High Learning" against
# "Commission on Higher Education" scores 2 of 4 — commission, higher — and that
# is below the line.
_NAME_MATCH_RATIO = 0.6

# Tokens too generic to count as an identifier on their own. "city" and "village"
# appear in almost every address in the country.
_LOCATION_STOPWORDS = frozenset({
    "city", "village", "barangay", "street", "st", "road", "rd", "floor",
    "unit", "brgy", "sitio", "purok",
})

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class Signals:
    """What the scan's own fields say, before any network call."""

    printed_name: str
    can_search: bool
    claimed_government: bool
    channels: list = field(default_factory=list)
    main_domain: str | None = None
    domains_disagree: bool = False
    has_location: bool = False
    location: str = ""
    registration_claim: str = ""
    has_registration_claim: bool = False
    job_title: str = ""


@dataclass(frozen=True)
class Entity:
    """What Round 1's results say they are about.

    Every field is a heuristic for choosing a query. None of them sets a status.
    """

    name: str = ""
    domain: str | None = None
    names_differ: bool = False
    shares_identifier: bool = False


@dataclass(frozen=True)
class PlannedQuery:
    """One follow-up, and the one thing it is for."""

    purpose: str
    text: str
    include_domains: tuple = ()

    def as_wire(self) -> dict:
        return {"purpose": self.purpose, "query": self.text}


@dataclass(frozen=True)
class LabelledResult:
    """One retrieved result, and where it came from.

    `describes_entity` says whether the page is about the organisation the
    resolver identified — **not** whether it matched the query. A page can match
    a query and be about a different body entirely, and that is the shape of the
    bug: the model reads a silent page about the wrong organisation as an absence
    of evidence about the right one.
    """

    url: str
    query: str
    describes_entity: bool


# ── helpers ────────────────────────────────────────────────────────────────


def entity_domain_of(domain: str) -> str:
    """The registrable part of a host, so a subdomain cannot become a scope.

    `www.ched.gov.ph` and `ched.gov.ph` are the same employer, and a scoped query
    naming the first would exclude the second.

    Delegates to `search.registrable_domain` rather than repeating the rule. Two
    copies of "which labels belong to the domain" is how the planner came to
    reduce `gov.ph` differently from the request that carries it, and the scope
    is then built from a domain the request never sees.
    """
    return registrable_domain(domain)


def search_query_is_safe(query: str) -> bool:
    """Whether a planned query may be issued.

    Word-bounded rather than a substring test: "Scamander Foods" is a company, and
    a substring check would drop a legitimate query about it.
    """
    lowered = (query or "").lower()
    words = set(re.findall(r"[a-z]+", lowered))
    return not any(term in words for term in _BANNED_QUERY_TERMS)


def _sanitise(query: str) -> str:
    """Strip control characters and cap the length.

    A query reaches Tavily verbatim, and both limits are ones the request model
    already applies to model-proposed queries.
    """
    cleaned = _CONTROL_CHARS.sub(" ", query or "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:MAX_VERIFY_QUERY_CHARS]


def _normalise_name(name: str) -> set:
    """Tokens of a name, minus the legal suffix and the filler words.

    "San Miguel Corporation" and "San Miguel Corp." must normalise to the same
    set, or every company with a suffix reads as a different name.
    """
    words = [w for w in re.findall(r"[a-z0-9]+", (name or "").lower()) if w]
    meaningful = [w for w in words if w not in _LEGAL_SUFFIXES]
    return set(meaningful or words)


def _host_of(value: str) -> str:
    """The domain behind a channel value, or "".

    Channels arrive as `"<type> | <value as printed>"`, and the value is an email
    address, a URL, a short link, a phone number, a street address or a handle.

    **The type decides.** A street address contains dots - "Room 5, Mabini St.,
    Iloilo City" - and reading it as a host produced the domain "room", which is
    not a domain, and which the planner would then spend one of its three
    credits querying. A phone number and a messaging handle have no host either.
    The typed format exists so that nothing has to be guessed from a separator,
    and this is where the guessing was happening.

    A value with **no** type falls back to the shape: an address, a handle and a
    phone number all contain whitespace or no dot, and a host contains neither.
    """
    raw = (value or "").strip()
    kind = ""
    if "|" in raw:
        head, _, tail = raw.partition("|")
        kind = head.strip().lower()
        raw = tail.strip()
    if kind in _HOSTLESS_CHANNEL_TYPES:
        return ""
    if "@" in raw:
        raw = raw.rsplit("@", 1)[1]
    elif raw.startswith(("http://", "https://")):
        raw = urlsplit(raw).netloc
    elif "." not in raw or any(ch.isspace() for ch in raw):
        return ""  # a phone number, a street address, a handle
    return entity_domain_of(raw)


def _classify_domain(domain: str) -> str:
    """Which of the five classes a domain belongs to."""
    if not domain:
        return ""
    if domain.endswith(".gov.ph"):
        return "gov_ph"
    if domain in _FREE_EMAIL_DOMAINS:
        return "free_email"
    if domain in _AGGREGATOR_DOMAINS:
        return "job_board"
    if domain.startswith("facebook.") or domain in {"messenger.com", "t.me", "wa.me"}:
        return "social"
    return "other"


# ── Round 0 ────────────────────────────────────────────────────────────────


def classify_signals(company_name: str, attributes: dict) -> Signals:
    """What the scan's fields say, with no network call.

    The contact channels matter most: one `gov_ph` domain beside another domain
    is the shape an impersonation takes, and it is visible here without a single
    credit spent.
    """
    attrs = attributes or {}
    name = (company_name or "").strip()

    channels: list[dict] = []
    raw_channel = str(attrs.get("CONTACT_METHOD") or "")
    for piece in raw_channel.split(";"):
        piece = piece.strip()
        if not piece:
            continue
        kind = piece.split("|", 1)[0].strip().lower() if "|" in piece else ""
        value = piece.split("|", 1)[1].strip() if "|" in piece else piece
        domain = _host_of(piece)
        channels.append({
            "type": kind,
            "value": value,
            "domain": domain,
            "class": _classify_domain(domain),
        })

    # The domain worth searching is the one that looks like the employer's own,
    # so free-mail and job boards never qualify — a query on them teaches nothing.
    ranked = [
        c for c in channels
        if c["domain"] and c["class"] in {"gov_ph", "other"}
    ]
    gov_first = [c for c in ranked if c["class"] == "gov_ph"]
    main_domain = (gov_first or ranked)[0]["domain"] if (gov_first or ranked) else None

    non_free = {c["domain"] for c in channels if c["domain"] and c["class"] in {"gov_ph", "other"}}
    domains_disagree = len(non_free) > 1

    location = str(attrs.get("LOCATION") or "").strip()
    registration = str(attrs.get("REGISTERED_AS") or "").strip()

    # The prompt's format line for `CLAIMED_TYPE` is a list of options, and a
    # model that copies it produces the whole list. "government | private
    # company | ..." is not the word "government", and reading it as anything
    # else loses the government claim silently - which is the claim the whole
    # fake-government case turns on. The first option is the answer.
    claimed_type = str(attrs.get("CLAIMED_TYPE") or "").strip().lower()
    claimed_type = claimed_type.split("|", 1)[0].strip()

    return Signals(
        printed_name=name,
        can_search=bool(name),
        claimed_government=claimed_type == "government",
        channels=channels,
        main_domain=main_domain,
        domains_disagree=domains_disagree,
        has_location=bool(location),
        location=location,
        registration_claim=registration,
        has_registration_claim=bool(registration),
        job_title=str(attrs.get("JOB_TITLE") or "").strip(),
    )


# ── Resolve ────────────────────────────────────────────────────────────────


def _entity_name_from_titles(results: list) -> str:
    """The organisation name the best results use.

    Titles carry a trailing "| Official Website" or a site name far more often
    than they carry pure prose, so the leading segment is the best available
    estimate. It is only ever used to pick queries.
    """
    for result in results or []:
        title = (result.title or "").strip()
        if not title:
            continue
        head = re.split(r"\s*[|–—-]\s*", title)[0].strip()
        if len(head) >= 4:
            return head
    return ""


def resolve_entity(signals: Signals, results: list) -> Entity:
    """What Round 1's results say they describe.

    **Heuristics for choosing queries only.** No field here sets a status, and the
    verify prompt remains the only thing that decides anything about an employer.
    A wrong `domain` produces a wrong scoped query, not a wrong assessment — which is
    why the aggregator denylist is a size-and-test question rather than a
    correctness one.
    """
    results = results or []
    if not results:
        return Entity()

    name = _entity_name_from_titles(results)

    printed_tokens = _normalise_name(signals.printed_name)
    entity_tokens = _normalise_name(name)
    overlap = len(printed_tokens & entity_tokens)
    names_differ = bool(printed_tokens) and overlap / len(printed_tokens) < _NAME_MATCH_RATIO

    # Prefer a .gov.ph host when the posting claims a government body, then the
    # best-ranked result that is not an aggregator.
    domain = None
    for result in results:
        host = _host_of(result.url or "")
        if not host or host in _AGGREGATOR_DOMAINS:
            continue
        if signals.claimed_government and host.endswith(".gov.ph"):
            domain = host
            break
        if domain is None:
            domain = host

    shares_identifier = False
    if signals.location:
        wanted = [
            w for w in re.findall(r"[a-z0-9]+", signals.location.lower())
            if len(w) >= 4 and w not in _LOCATION_STOPWORDS
        ]
        if wanted:
            for result in results:
                haystack = f"{result.title} {result.snippet}".lower()
                if sum(1 for w in wanted if w in haystack) >= 2:
                    shares_identifier = True
                    break

    return Entity(
        name=name,
        domain=domain,
        names_differ=names_differ,
        shares_identifier=shares_identifier,
    )


# ── Round 2 ────────────────────────────────────────────────────────────────


def _planner_rows(signals: Signals, entity: Entity) -> list:
    """The decision table, in priority order. First matching rows, up to the cap.

    **Row 1 fires on `names_differ` alone.** An earlier draft required a shared
    address as well, and that trigger does not fire on the case it was written
    for: the live run's results for the CHED flyer were US accreditors with no
    Iloilo in them, so there was no address to share. The absence of one is what
    the failure looks like.
    """
    rows = []

    if entity.names_differ and signals.main_domain:
        rows.append(PlannedQuery(
            purpose="the poster's own domain: does anything exist for it, and is it the entity's",
            text=signals.main_domain,
        ))

    if entity.names_differ and entity.shares_identifier and entity.domain:
        title = signals.job_title or "hiring"
        rows.append(PlannedQuery(
            purpose="whether this role is posted on the entity's own site",
            text=f"{title} {entity.name}".strip(),
            include_domains=(entity.domain,),
        ))

    if signals.location:
        rows.append(PlannedQuery(
            purpose="a footprint for the printed name, located",
            text=f"{signals.printed_name} {signals.location}".strip(),
        ))

    if signals.has_registration_claim:
        rows.append(PlannedQuery(
            purpose="testing the registration the posting claims for itself",
            text=f"{signals.registration_claim} {signals.printed_name}".strip(),
        ))

    return rows


def plan_followups(
    signals: Signals,
    entity: Entity,
    round1_ok: bool,
    model_queries: list | None = None,
) -> list:
    """The follow-up queries for this verification, in the order they should run.

    **A failed Round 1 plans nothing.** Credits are never spent against a
    provider that has just failed.

    Model-proposed queries are **filler**: used only when the table leaves slots
    empty, so a credit is never spent on a duplicate of the anchor query when the
    planner had a better use for it. They are not retired, because no table can
    anticipate every question — `Similar Offers` has no row, and the scan prompt
    spends a query on it deliberately.
    """
    if not round1_ok:
        return []

    planned: list = []
    for row in _planner_rows(signals, entity):
        text = _sanitise(row.text)
        if not text or not search_query_is_safe(text):
            continue
        planned.append(PlannedQuery(
            purpose=row.purpose,
            text=text,
            # Only ever a domain taken from Round 1's results, never from the
            # posting. Scoping discovery to the domain under suspicion would
            # restrict the search to the thing being tested.
            include_domains=tuple(row.include_domains) if row.include_domains and entity.domain else (),
        ))
        if len(planned) >= MAX_FOLLOWUPS:
            return planned

    for raw in model_queries or []:
        if len(planned) >= MAX_FOLLOWUPS:
            break
        text = _sanitise(str(raw))
        if not text or not search_query_is_safe(text):
            log.warning("[search] Dropped a model query that failed the term check: %r", text)
            continue
        if text == signals.printed_name:
            continue
        planned.append(PlannedQuery(purpose="a question the planner did not anticipate", text=text))

    return planned


# ── Labelling ──────────────────────────────────────────────────────────────


def _mentions(text: str, tokens: set) -> bool:
    """Whether a result's own words carry enough of the entity's name.

    Measured the same way `names_differ` is — against the entity's tokens — so
    both use one definition of "is this the same organisation" rather than two
    that can disagree.
    """
    if not tokens:
        return False
    words = set(re.findall(r"[a-z0-9]+", (text or "").lower()))
    return len(tokens & words) / len(tokens) >= _NAME_MATCH_RATIO


def label_results(results: list, entity: Entity, query_of: dict) -> dict:
    """Attach each result's originating query and whether it is about `entity`.

    **Every merged result is labelled, and none is dropped.** Dropping evidence is
    how the entity heuristic goes wrong in the first place: a result that turns
    out to matter cannot be recovered once discarded. Labelling lets the model
    discount a page about the wrong body while the page stays available to
    contradict us if it should.

    `query_of` maps a result's URL to the query that retrieved it. A URL the map
    does not know — the dedupe kept it, some earlier call supplied it — is
    labelled with an empty query rather than dropped, because a result with no
    provenance is still evidence.
    """
    entity_tokens = _normalise_name(entity.name)
    labelled: dict = {}
    for result in results or []:
        url = getattr(result, "url", "") or ""
        if url in labelled:
            continue
        body = f"{getattr(result, 'title', '')} {getattr(result, 'snippet', '')}"
        labelled[url] = LabelledResult(
            url=url,
            query=query_of.get(url, ""),
            describes_entity=_mentions(body, entity_tokens) if entity.name else False,
        )
    return labelled