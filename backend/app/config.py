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
    ai_temperature: float = 0.2
    ai_top_p: float = 1.0
    ai_max_tokens: int = 2048
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
    # Credit cost lives here, not in the code. Advanced depth costs 2 credits
    # against basic's 1, so it halves the monthly budget in exchange for better
    # recall on a small local employer. That is the right default and the wrong
    # one for a deployment being run down its quota, so it is an env value.
    tavily_search_depth: str = "advanced"
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
