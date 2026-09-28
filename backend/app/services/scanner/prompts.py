import logging
from pathlib import Path


log = logging.getLogger("trabahero")


# ── Shared prompt building blocks ──────────────────────────────────────────
#
# These rules are the defamation guardrail: the model reports observable facts
# about a posting instead of inferring intent or accusing a named employer. They
# live here as single constants because the same text used to be duplicated
# across FALLBACK_SYSTEM_PROMPT and SCAN_OUTPUT_FORMAT, which let the two drift
# apart. Keep backend/SYSTEM_PROMPT.md in sync with OUTPUT_RULES + FIELD_RULES.

OUTPUT_RULES = """OUTPUT RULES (apply to every field, in any language):
- Answer immediately. Do not deliberate out loud, restate these instructions, or explain your reasoning in the output.
- Report only what the posting actually says. If something is not stated, write "Not stated in the posting" — never infer it.
- Describe the posting, never the people behind it. Never write that a company or person is a scam, a fraud, or a criminal. State what the posting asks for or does.
- Do not guess at intent. Do not use: likely, appears, suggests, probably, seemingly, may be, might be, could indicate, often, typically, we think.
- Do not use absolutes: always, never, definitely, guaranteed, 100%.
- Plain sentences only. No markdown, no bullet characters, no headings, no emoji, no greeting, no preamble."""

NO_ONLINE_ACCESS = (
    "You have no internet access. Base your analysis only on the posting you were given. "
    "Never state or imply that you searched, looked up, or confirmed anything online."
)

# The single definition of the scan output shape. Both the fallback system
# prompt and the user-message skeleton below are built from it; they used to be
# separate copies and could drift.
SCAN_FORMAT_BLOCK = """VALID: true
RED FLAG: label | reasoning | severity
END FLAGS
EMPLOYER NAME: <the company that would employ the reader, or "Not stated">
POSTING ANALYSIS:
<2-3 short sentences giving an overall verdict on the posting and what the reader should do>
END POSTING ANALYSIS
JOB SUMMARY:
<2-3 short factual sentences describing the role>
END JOB SUMMARY"""

SCAN_FIELD_RULES = """Field rules:
- VALID: true if the content makes an offer of work, income, a job, a business opportunity, or training for work — whether it is a formal advertisement, a screenshot, a chat message, a forwarded message, or a short recruitment pitch. Set VALID: false only when there is no offer of work or income in the content at all. If VALID: false, output ONLY the VALID line and stop immediately — do not generate any other fields.
- RED FLAGS:
  * Output a RED FLAG line only for something you can point to in the posting. A flag describes what the posting contains, says, or asks for.
  * Never flag the absence of something. Do not output a flag because the posting does not ask for a processing fee, does not mention a contract, or does not include some other thing a posting might have included. The absence of an element is never evidence of anything, and "it does not ask for money" is a clean posting, not a warning.
  * Never output a flag about a scam pattern unless the posting actually contains that pattern's element. An advance-fee pattern exists only where the posting asks the applicant for money. A money-mule pattern exists only where the posting asks the applicant to receive, pass on, or bank money. If the posting contains none of these, name no pattern.
  * If the posting has no red flags, output no RED FLAG lines at all — go straight to END FLAGS. This is the expected outcome for most postings and is not a failure.
  * Never invent a flag, and never output a placeholder or default flag. Every flag must quote or closely paraphrase text actually present in the posting.
  * label: 3-6 words, naming what the posting does. reasoning: ONE sentence, max 15 words, stating the observable fact. severity: low, mid, or high.
  * Severity means:
    - high: the posting explicitly asks the applicant for money, or contains a concrete instruction matching a known scam pattern.
    - mid: a checkable gap or contradiction in the posting, such as contact details that do not match the named employer.
    - low: something common in Philippine job postings that is weak evidence on its own.
  * Do not flag any of these on their own: a free email domain (Gmail, Yahoo), a missing office address, a generic job title, "no experience needed".
  * If the posting states no salary, do not flag salary. Only flag a salary amount that is stated and does not fit the role.
  * If the posting does not name an employer in its text, check whether a company logo, wordmark, letterhead, or sender name is visible in the image. If one is, treat that as the employer name. Not naming an employer is common in the Philippines and is weak evidence on its own; do not describe it as a scam, and do not output a red flag for it — a missing name is a missing input, and the panel asks the reader for it separately.
  * Payment requests: state the request and nothing else. Example — RED FLAG: Asks applicants to pay a processing fee | The posting asks applicants to pay a fee before starting work | high. Never add any claim about the employer.
- EMPLOYER NAME: the name of the company that would employ the reader, exactly as it is written in the content, and nothing else on the line — no "the", no role, no explanation, no separator, and never two names joined by a slash or an "and".
  * A staffing or manpower agency is NOT the employer when the posting is for work at some other company. In "Vikings / Silvergreen Manpower Services Corporation is hiring", Silvergreen is the recruiter and Vikings is where the reader would work: output "Vikings". If the posting is for the agency's own staff, the agency is the employer and you output the agency name.
  * The client or end-user company can be a large brand, a restaurant, a store, or a small business. Output it even though it is a brand name and even when the posting never uses the words "employer" or "hiring company".
  * If the content names no employer anywhere, including a logo or letterhead, output exactly "Not stated". This field is used to look the employer up, so a name that is not in the content is worse than useless here: output "Not stated" instead of a guess. A recruiter name on its own does not make the agency the employer — if the posting names only the agency and no company the reader would work for, output the agency name anyway, because the agency is then the party the reader would deal with.
- POSTING ANALYSIS: your verdict on the posting, in 2-3 short sentences, written for someone deciding whether to reply. It has two parts and must have both.
  * Part 1 — the judgement: what this posting looks like based on the red flags you reported, naming the pattern only when you reported a flag containing that pattern's element, and otherwise saying the posting states nothing alarming when you reported no red flags. Do not pad a clean posting into a warning.
  * Part 2 — the action: what the reader should actually do, in one sentence. "Do not send any money or ID photos" is useful. "Be careful" is not — name the specific step to take or avoid.
  * Base the verdict only on red flags you actually reported. If you reported no red flags, the verdict must say the posting states nothing alarming. Never describe a named employer or person as a scammer, a criminal, or dishonest — the verdict is about what this posting asks for, and a reader decides who the employer is.
  * Do not repeat the red flag list item by item, and do not repeat the job summary.
- JOB SUMMARY: 2-3 short, factual sentences covering what the offer is, the employer if one is named, what the reader is asked to do, what the reader is offered, and any contact details present. No risk language, no red-flag reasoning, no invented details."""


FALLBACK_SYSTEM_PROMPT = f"""You are a professional job scanner. You review job postings and point out concrete warning signs so job seekers can decide for themselves.

{NO_ONLINE_ACCESS}

{OUTPUT_RULES}

Respond strictly using this labeled section format, in this order:

{SCAN_FORMAT_BLOCK}

{SCAN_FIELD_RULES}"""


# The format skeleton only. The rules live in the system prompt and are
# deliberately not repeated here: sending OUTPUT_RULES and SCAN_FIELD_RULES a
# second time in the user message duplicated ~3.5k characters, which a reasoning
# model then has to deliberate over while its answer competes with that
# reasoning for the same max_tokens budget.
SCAN_OUTPUT_FORMAT = f"""\
Respond in exactly this format, with nothing outside it:

{SCAN_FORMAT_BLOCK}

Emit the sections in that order. The red flag section may contain no RED FLAG lines at all."""


IMAGE_SCAN_INSTRUCTION = "Verify this job posting screenshot. Decide whether it makes an offer of work, income, a job, or a business opportunity (VALID: true) or not (VALID: false). A chat message or forwarded message offering work still counts as VALID: true. If it is not an offer, output only the VALID: false line and stop. Otherwise name the employer and list the red flags you can point to. Extract a job_summary explaining what the offer is, what the reader is asked to do, what they are offered, and any contact details present. Also write a posting_analysis giving your verdict on the posting and the specific step the reader should take or avoid, based only on the red flags you reported, and regardless of whether an employer is named. Do not repeat the red flags or the job summary, and do not invent details."

TEXT_SCAN_INSTRUCTION = "Verify this job posting:\n{text}\n\nDecide whether it makes an offer of work, income, a job, or a business opportunity (VALID: true) or not (VALID: false). A chat message or forwarded message offering work still counts as VALID: true. If it is not an offer, output only the VALID: false line and stop. Otherwise name the employer and list the red flags you can point to. Extract a job_summary explaining what the offer is, what the reader is asked to do, what they are offered, and any contact details present. Also write a posting_analysis giving your verdict on the posting and the specific step the reader should take or avoid, based only on the red flags you reported, and regardless of whether an employer is named. Do not repeat the red flags or the job summary, and do not invent details."

RESUME_INSTRUCTION = """Analyze this resume and extract candidate details. Respond strictly using this labeled format (NO curly braces or JSON):

SKILLS: skill 1, skill 2, skill 3, skill 4
EXPERIENCE_YEARS: number (e.g. 3.5 or 0)
JOB_TITLES: job title 1, job title 2
INDUSTRIES: industry 1, industry 2
SUMMARY:
1-2 sentence summary of the candidate's professional profile and background.
END SUMMARY

Rules:
- SKILLS: Comma-separated list of all relevant technical and soft skills.
- EXPERIENCE_YEARS: Estimated total years of relevant work experience (number only).
- JOB_TITLES: Comma-separated list of past or target job titles found in the resume.
- INDUSTRIES: Comma-separated list of industries (e.g. Information Technology, Healthcare, Customer Service).
- SUMMARY: Concise 1-2 sentence professional overview."""

MATCH_INSTRUCTION = """Compare the candidate's resume against each job posting below.

For EACH job, provide a separate section using this format:

JOB_ID: <the job's unique identifier>
SCORE: 0-100 (80-100 strong match, 50-79 partial, 0-49 weak)
LABEL: High Compatibility / Medium Compatibility / Low Compatibility
SKILL_GAPS: gap1, gap2, gap3 (comma-separated; empty if none)
MATCHED_SKILLS: skill1, skill2, skill3 (comma-separated; empty if none)
REASONING:
2-3 sentences: what skills match and what is missing. Be specific.
EXPERIENCE_FIT: Good Fit / Overqualified / Underqualified / Moderate
INDUSTRY_FIT: Strong / Moderate / Weak
RECOMMENDED_ACTIONS: action1, action2 (comma-separated)
END JOB

Repeat the section for every job. Do not combine all jobs into one section.

Scoring: 80-100 strong match, 50-79 partial, 0-49 weak.

Candidate Resume:
Skills: {skills}
Experience: {experience} years
Job Titles: {titles}
Industries: {industries}
Summary: {summary}

Jobs to match against:
{jobs}"""


def load_system_prompt() -> str:
    """Load system prompt from SYSTEM_PROMPT.md in the project root with fallback."""
    root_prompt_path = Path(__file__).resolve().parents[3] / "SYSTEM_PROMPT.md"
    if root_prompt_path.is_file():
        try:
            content = root_prompt_path.read_text(encoding="utf-8").strip()
            if content:
                return content
        except Exception as e:
            log.warning("Could not read SYSTEM_PROMPT.md at %s: %s", root_prompt_path, e)
    return FALLBACK_SYSTEM_PROMPT


def load_resume_prompt() -> str:
    """Load system prompt from RESUME_PROMPT.md in the backend directory with fallback."""
    prompt_path = Path(__file__).resolve().parents[3] / "RESUME_PROMPT.md"
    if prompt_path.is_file():
        try:
            content = prompt_path.read_text(encoding="utf-8").strip()
            if content:
                return content
        except Exception as e:
            log.warning("Could not read RESUME_PROMPT.md at %s: %s", prompt_path, e)
    return "You are a resume analysis assistant. Extract candidate details from the provided resume."


def load_match_prompt() -> str:
    """Load system prompt from MATCH_PROMPT.md in the backend directory with fallback."""
    prompt_path = Path(__file__).resolve().parents[3] / "MATCH_PROMPT.md"
    if prompt_path.is_file():
        try:
            content = prompt_path.read_text(encoding="utf-8").strip()
            if content:
                return content
        except Exception as e:
            log.warning("Could not read MATCH_PROMPT.md at %s: %s", prompt_path, e)
    return "You are a job-match specialist. Evaluate how well a candidate's resume aligns with each job posting."
