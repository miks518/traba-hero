from app.ai_limiter import ai_limiter
from app.services.search import build_queries, clean_company_name, extract_company_name, is_valid_company_name, merge_results, search
from app.services.email_verifier import verify_emails_in_text
from app.services.lm_client import (
    _parse_custom,
    _parse_json,
    _parse_match_custom,
    _parse_resume_custom,
    _structured_output_body,
    chat,
    chat_stream_pieces,
)

from .offer_parser import _parse_analyze_offer
from .offer_prompt import ANALYZE_OFFER_RESPONSE_SCHEMA, ANALYZE_OFFER_SYSTEM_PROMPT, _build_analyze_offer_prompt
from .risk_calculator import (
    _calculate_risk_score_from_verify,
    _combine_scores,
    _posting_risk_from_flags,
)
from .scan_result import _VALID_LINE_RE, _red_flags, _scan_response
from .sse import _sse
from .verification_parser import _missing_categories, _parse_verification_result, _parse_verify_section
from .verification_prompt import (
    VERIFY_SYSTEM_PROMPT,
    VERIFY_RESPONSE_SCHEMA,
    _build_verify_prompt,
    format_results,
)


class ScannerDependencies:
    get_chat_stream = staticmethod(lambda: chat_stream_pieces)
    get_verify_emails = staticmethod(lambda: verify_emails_in_text)
    get_extract_company = staticmethod(lambda: extract_company_name)
    get_clean_company_name = staticmethod(lambda: clean_company_name)
    get_parse_custom = staticmethod(lambda: _parse_custom)
    get_parse_json = staticmethod(lambda: _parse_json)
    get_company_name_is_valid = staticmethod(lambda: is_valid_company_name)
    get_response_factory = staticmethod(lambda: _scan_response)
    get_red_flags = staticmethod(lambda: _red_flags)
    get_valid_line_re = staticmethod(lambda: _VALID_LINE_RE)
    get_sse = staticmethod(lambda: _sse)
    get_parse_resume = staticmethod(lambda: _parse_resume_custom)
    get_parse_match = staticmethod(lambda: _parse_match_custom)
    get_search = staticmethod(lambda: search)
    get_build_queries = staticmethod(lambda: build_queries)
    get_merge_results = staticmethod(lambda: merge_results)
    get_format_results = staticmethod(lambda: format_results)
    get_chat = staticmethod(lambda: chat)
    get_build_verify_prompt = staticmethod(lambda: _build_verify_prompt)
    get_parse_verification_result = staticmethod(lambda: _parse_verification_result)
    get_parse_verify_section = staticmethod(lambda: _parse_verify_section)
    get_missing_categories = staticmethod(lambda: _missing_categories)
    get_calculate_risk = staticmethod(lambda: _calculate_risk_score_from_verify)
    get_verify_system_prompt = staticmethod(lambda: VERIFY_SYSTEM_PROMPT)
    get_verify_response_format = staticmethod(
        lambda: _structured_output_body(VERIFY_RESPONSE_SCHEMA, "verification_result")
    )
    get_ai_limiter = staticmethod(lambda: ai_limiter)
    get_posting_risk = staticmethod(lambda: _posting_risk_from_flags)
    get_combine_scores = staticmethod(lambda: _combine_scores)
    get_analyze_offer_prompt = staticmethod(lambda: ANALYZE_OFFER_SYSTEM_PROMPT)
    get_analyze_offer_response_format = staticmethod(
        lambda: _structured_output_body(ANALYZE_OFFER_RESPONSE_SCHEMA, "offer_analysis")
    )
    get_build_analyze_offer_prompt = staticmethod(lambda: _build_analyze_offer_prompt)
    get_parse_analyze_offer = staticmethod(lambda: _parse_analyze_offer)


runtime = ScannerDependencies()

__all__ = ["ScannerDependencies", "runtime"]
