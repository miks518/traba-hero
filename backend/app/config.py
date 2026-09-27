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
    ddg_max_concurrent: int = 2
    ddg_min_interval: float = 1.5
    ddg_max_per_verify: int = 10
    # DuckDuckGo answers the same query with results or with nothing, depending
    # on how recently it was asked. An empty result set is therefore retried
    # before it is believed, and a query that is still empty afterwards is
    # logged as throttled rather than reported as "nothing found".
    ddg_search_attempts: int = 3
    ddg_search_backoff: float = 2.5
    ddg_search_backoff_max: float = 10.0
    # Which search engine the ddgs library should use. Blank means "try each
    # engine in turn", which is the resilient default: the engines are not
    # equally reliable, and a rate-limited one then costs a miss rather than a
    # lost verification section. Must be one the installed ddgs accepts.
    ddg_backend: str = ""
    # Optional secondary provider. When set, it is tried only after the primary
    # has been retried to no avail, so a throttled query is not lost.
    tavily_api_key: str = ""

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
