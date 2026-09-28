"""Verification prompt and its output schema.

The output is a JSON Schema rather than a labeled text format. The custom format
existed because the native model web search broke on curly braces; searches now
run in the backend and the model only reads the results, so structured output is
safe. The guardrail prose below is unchanged — the schema constrains the *shape*,
not the wording, so every rule about what may be claimed still has to be said.
"""

from app.models.schemas import VerifyRequest


VERIFY_SYSTEM_PROMPT = """You are a job verification assistant. You are given web search results about a company. Report what those search results actually show, nothing more.

OUTPUT RULES (apply to every field, in any language):
- Report only what the provided search results state. If a result does not cover a category, say so plainly. Never fill a gap with what you know about the company from training.
- Never claim you checked a website, registry, or social account that is not in the provided results.
- Describe findings, never the people behind them. Never write that a company or person is a scam, a fraud, or a criminal. State what a result says.
- Do not guess at intent. Do not use: likely, appears, suggests, probably, seemingly, may be, might be, could indicate, often, typically, we think.
- Do not use absolutes: always, never, definitely, guaranteed, 100%.
- Plain sentences only. No markdown, no bullet points, no headers, no emoji.

Analyze the provided search results and report on exactly these three categories. Report only these three. Do not invent a separate category for the company name, for social media presence, or for anything else.

1. Company Existence — whether the results show an active, operating business under the searched name, including any official website or listing they mention
2. SEC Registration — whether any result mentions Philippine SEC registration
3. Reputation — whether any result describes a scam report, fraud warning, formal complaint, or employee experience

Fill the "checks" array with one entry per category, using these exact values in "category": "Company Existence", "SEC Registration", "Reputation". Include all three whenever any result is present.

STATUS RULES for each check:
- green: a result in the provided results states the fact directly.
- yellow: the results are partial, ambiguous, conflicting, or say nothing about this category. THIS IS THE DEFAULT — when you did not find something, use yellow.
- red: a result in the provided results states a negative fact about this category (for example, a published scam report or fraud notice). The detail must name what that result says.

Absence of a result is NEVER red. "No scam reports found in the provided results" is yellow, not red. Only use red when a provided result actually states the negative, and quote or name that source in the detail.

FIELD RULES:
- detail: one sentence, max 20 words. Name the specific result you relied on, or state that the provided results contain nothing on this topic. Do not infer beyond the results and do not describe the company or anyone behind it.
- report: 2-3 plain sentences describing what the provided results show. No accusations. End by noting that this is based on public web search results only.
- recommendation: 1-2 plain sentences telling the user what to do next, phrased as a step they can take. Do not tell them what to think about the company."""


# Strict schemas must declare every property required and disallow extras, or
# the provider rejects the request.
VERIFY_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "checks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["Company Existence", "SEC Registration", "Reputation"],
                    },
                    "status": {"type": "string", "enum": ["green", "yellow", "red"]},
                    "detail": {"type": "string"},
                },
                "required": ["category", "status", "detail"],
                "additionalProperties": False,
            },
        },
        "report": {"type": "string"},
        "recommendation": {"type": "string"},
    },
    "required": ["checks", "report", "recommendation"],
    "additionalProperties": False,
}


NO_SEARCH_RESULTS = """=== SEARCH RESULTS FOR: {company} ===
No search results were returned for this company. The search produced nothing,
which may mean the company has no online presence, or that the search failed.

This is NOT evidence that the company is fraudulent. It is an absence of
information. Report every category as yellow, state in each detail that the
search returned no results, and do not use anything you know about this company
from training. Write a recommendation telling the reader to confirm the employer
through an official channel before sending personal details.
=== END SEARCH ==="""


def _build_verify_prompt(req: VerifyRequest, search_context: str = "") -> str:
    """Build the user prompt for verification.

    Only the search results go in. The job summary and the posting's red flags
    used to be sent as well, and both are actively harmful here: the model is
    asked to report what the search shows about a company, and handing it
    "Asks applicants to pay a processing fee" invites it to answer about the
    posting instead of the employer — a red flag about the posting is not a fact
    about the company, and it belonged to the posting-stage score. The company
    name is kept because the results are keyed to it.
    """
    parts = []
    if req.company_name:
        parts.append(f"Company to verify: {req.company_name}")
    if search_context:
        parts.append(f"\n{search_context}")
    else:
        # Silently omitting the block left the system prompt claiming results had
        # been provided when none had. Say so explicitly so a retrieval failure
        # is reported as missing information rather than as a clean company.
        parts.append(
            "\n"
            + NO_SEARCH_RESULTS.format(company=req.company_name or "the employer")
        )
    return "\n\n".join(parts)
