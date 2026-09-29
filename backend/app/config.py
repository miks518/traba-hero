from pydantic import field_validator
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    ai_api_key: str = ""
    ai_api_url: str = ""
    openrouter_api_key: str = ""
    openai_api_key: str = ""
    model_name: str = ""
    # Per-endpoint model overrides. The scan and the verification ask for very
    # different things — prose in a labelled format versus a JSON object matching
    # a schema — and only some models have an endpoint OpenRouter can route a
    # schema request to. One MODEL_NAME forces the looser call onto the stricter
    # model's compromises, so these let a deployment choose per call. Blank (the
    # default) means the shared MODEL_NAME, leaving an existing deployment
    # unchanged. See resolve_model().
    ai_model_scan: str = ""
    ai_model_verify: str = ""
    ai_temperature: float = 0.2
    ai_top_p: float = 1.0
    ai_max_tokens: int = 2048
    # Per-endpoint budget overrides, mirroring AI_MODEL_SCAN / AI_MODEL_VERIFY.
    # Every endpoint used to pass a hardcoded max_tokens, so this setting was
    # honoured by the scan alone and the other four silently ignored it — the
    # literals were all equal to the default, which is what kept the skew
    # invisible. Blank (the default) means the shared AI_MAX_TOKENS. The offer
    # call follows the verify budget: both request schema-enforced JSON.
    # See resolve_max_tokens().
    ai_max_tokens_scan: str = ""
    ai_max_tokens_verify: str = ""
    # Reasoning models draw their deliberation from the same max_tokens budget
    # that must hold the answer, so a long think can end the response with no
    # content at all. OpenRouter's normalized "reasoning" parameter can cap the
    # thinking separately, or switch it off entirely. None leaves the provider
    # default alone; True forces reasoning on; False turns it off.
    ai_reasoning_enabled: bool | None = None
    ai_reasoning_max_tokens: int = 0
    ai_reasoning_effort: str = ""
    send_system_prompt: bool = True
    ai_max_concurrent: int = 2
    ai_max_queue_depth: int = 10
    ai_acquire_timeout: float = 10.0
    ai_call_timeout: float = 120.0
    client_secret_key: str = ""
    # Web search. Tavily's free tier is 1,000 credits/month and needs no card.
    # A missing key makes every search report as a failure rather than an empty
    # result, so a broken deployment cannot look like a clean employer.
    tavily_api_key: str = ""
    # Results per verification. Credits are charged per request, so this is
    # free — what it costs is context, since every snippet becomes prompt text
    # for a model that draws its reasoning from the same AI_MAX_TOKENS budget
    # that has to hold the answer. Env value so a deployment can trade the two.
    tavily_max_results: int = 4
    # Credit cost lives here, not in the code. A verification now issues two
    # queries (existence, then registration), so `basic` is 2 credits per
    # verification — the same as one `advanced` request was before the split.
    # `advanced` is therefore twice the price it looks like, and the budget
    # arithmetic in .env.example assumes the default.
    tavily_search_depth: str = "basic"
    # Tavily's `country` boost, which prioritises results from that country.
    # Blank disables the boost and issues the plain query.
    tavily_country: str = "philippines"
    # Tavily's `exclude_domains`, as a comma- or space-separated list. Unlike
    # `include_domains`, this *removes* pages rather than restricting the search
    # to a whitelist, so it does not fight the country boost: the JobStreet,
    # Indeed PH and PESO pages the boost exists to surface stay in the result
    # set unless named here.
    #
    # Wikipedia is excluded by default because it is not a source. A crowd-edited
    # entry is unattributed and often wrong, and this panel is asked to state
    # facts about a named company — citing one would be a claim nobody can trace
    # back to whoever asserted it. Everything else is a deployment decision.
    tavily_exclude_domains: str = "wikipedia.org"

    @field_validator("ai_reasoning_enabled", mode="before")
    @classmethod
    def _blank_optional_bool_is_unset(cls, value):
        """A blank line in a .env means "not configured", not "invalid".

        `.env.example` ships this key blank and tells the reader to leave it
        blank, but a bare `bool | None` cannot parse an empty string, so a fresh
        copy of the example crashed at import. Only blank is coerced: a real
        value like "maybe" still raises, because silently treating nonsense as
        unset would leave reasoning at the provider default while the operator
        believed they had configured it.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value

    def resolve_model(self, endpoint: str) -> str:
        """The model for one endpoint, falling back to the shared MODEL_NAME.

        Blank is treated as unset rather than sent, because an empty model ID is
        itself a 404 and a blank line in a `.env` is the easiest way to produce
        one. An unrecognised endpoint name resolves to the shared model too, so a
        typo in a caller degrades to today's behaviour instead of naming a model
        that does not exist.
        """
        overrides = {
            "scan": self.ai_model_scan,
            "verify": self.ai_model_verify,
            "offer": self.ai_model_verify,
        }
        chosen = overrides.get(endpoint, "").strip()
        return chosen or self.model_name.strip()

    def resolve_max_tokens(self, endpoint: str) -> int:
        """The token budget for one endpoint, falling back to AI_MAX_TOKENS.

        Anything that is not a positive integer is treated as unset: a blank
        line, a stray word, or a zero. A bad `max_tokens` is a request the
        provider may reject outright, so a typo in a cost setting must not
        become a failure — it costs answer length, nothing else.
        """
        overrides = {
            "scan": self.ai_max_tokens_scan,
            "verify": self.ai_max_tokens_verify,
            "offer": self.ai_max_tokens_verify,
        }
        chosen = overrides.get(endpoint, "").strip()
        if chosen.isdigit() and int(chosen) > 0:
            return int(chosen)
        return self.ai_max_tokens

    @property
    def tavily_search_depth_fallback(self) -> str:
        """A depth Tavily accepts, for a configured value it might not.

        Sending "advnaced" would have the provider reject the request, turning
        a configuration typo into a search failure reported to the user as an
        employer that cannot be looked up. A typo costs recall, not a verdict.
        """
        return "basic" if self.tavily_search_depth.strip().lower() == "basic" else "advanced"

    @property
    def effective_ai_api_key(self) -> str:
        for key in (self.ai_api_key, self.openrouter_api_key, self.openai_api_key):
            if key and key.strip():
                return key.strip()
        return ""

    @property
    def effective_ai_url(self) -> str:
        if self.ai_api_url and self.ai_api_url.strip():
            return self.ai_api_url.strip()
        return "https://openrouter.ai/api/v1"

    model_config = {
        "env_file": os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
