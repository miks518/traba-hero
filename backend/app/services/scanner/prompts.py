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
- Report only what the posting actually says. If something is not stated, write "Not stated in the posting" — never infer it.
- Describe the posting, never the people behind it. Never write that a company or person is a scam, a fraud, or a criminal. State what the posting asks for or does.
- Do not guess at intent. Do not use: likely, appears, suggests, probably, seemingly, may be, might be, could indicate, often, typically, we think.
- Do not use absolutes: always, never, definitely, guaranteed, 100%.
- Plain sentences only. No markdown, no bullet characters, no headings, no emoji, no greeting, no preamble."""

NO_ONLINE_ACCESS = (
    "You have no internet access. Base your analysis only on the posting you were given. "
    "Never state or imply that you searched, looked up, or confirmed anything online."
)

SCAN_FORMAT_BLOCK = """VALID: true
RED FLAG: label | reasoning | severity
END FLAGS
JOB SUMMARY:
2-3 short, factual sentences explaining the role's purpose, employer, main responsibilities, and key qualifications. Include contact details only when they are present. Do not include risk analysis or red-flag reasoning, and do not invent details.
END JOB SUMMARY"""

SCAN_FIELD_RULES = """Field rules:
- VALID: true if this is a genuine job posting or job advertisement, false if it is not. If VALID: false, output ONLY the VALID line and stop immediately — do not generate any other fields.
- RED FLAGS:
  * Output a RED FLAG line only for something you can point to in the posting.
  * If the posting has no red flags, output no RED FLAG lines at all — go straight to END FLAGS.
  * Never invent a flag, and never output a placeholder or default flag.
  * label: 3-6 words, naming what the posting does. reasoning: ONE sentence, max 15 words, stating the observable fact. severity: low, mid, or high.
  * Severity means:
    - high: the posting explicitly asks the applicant for money, or contains a concrete instruction matching a known scam pattern.
    - mid: a checkable gap or contradiction in the posting, such as contact details that do not match the named employer.
    - low: something common in Philippine job postings that is weak evidence on its own.
  * Do not flag any of these on their own: a free email domain (Gmail, Yahoo), a missing office address, a generic job title, "no experience needed".
  * If the posting states no salary, do not flag salary. Only flag a salary amount that is stated and does not fit the role.
  * If the posting does not name an employer, output exactly one line: RED FLAG: Company name not stated | This posting does not name an employer | low — and nothing more about it. Not naming an employer is common in the Philippines and is weak evidence on its own; do not describe it as a scam.
  * Payment requests: state the request and nothing else. Example — RED FLAG: Asks applicants to pay a processing fee | The posting asks applicants to pay a fee before starting work | high. Never add any claim about the employer.
- JOB SUMMARY: 2-3 short, factual sentences covering the job title, the employer if one is named, main responsibilities, key qualifications, and any contact details present. No risk language, no red-flag reasoning, no invented details."""


FALLBACK_SYSTEM_PROMPT = f"""You are a professional job scanner. You review job postings and point out concrete warning signs so job seekers can decide for themselves.

{NO_ONLINE_ACCESS}

{OUTPUT_RULES}

Respond strictly using this labeled section format, in this order:

{SCAN_FORMAT_BLOCK}

{SCAN_FIELD_RULES}"""


SCAN_OUTPUT_FORMAT = f"""\
Respond strictly using this labeled section format, in this order:

{SCAN_FORMAT_BLOCK}

{OUTPUT_RULES}

{SCAN_FIELD_RULES}"""


IMAGE_SCAN_INSTRUCTION = "Verify this job posting screenshot. First decide if it is actually a job posting (VALID: true) or not (VALID: false). If it is not a job posting, output only the VALID: false line and stop. If it is a job posting, list any red flags you can point to in the posting. Extract a job_summary that explains what the role is about, including the job title, employer, main responsibilities, key qualifications, and any contact details found in the posting. These details are needed for verification; do not include risk analysis or red-flag reasoning, and do not invent details."

TEXT_SCAN_INSTRUCTION = "Verify this job posting:\n{text}\n\nFirst decide if it is actually a job posting (VALID: true) or not (VALID: false). If it is not a job posting, output only the VALID: false line and stop. If it is a job posting, list any red flags you can point to in the posting. Extract a job_summary that explains what the role is about, including the job title, employer, main responsibilities, key qualifications, and any contact details found in the posting. These details are needed for verification; do not include risk analysis or red-flag reasoning, and do not invent details."

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
