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
    send_system_prompt: bool = True
    ai_max_concurrent: int = 2
    ai_max_queue_depth: int = 10
    ai_acquire_timeout: float = 10.0
    ai_call_timeout: float = 120.0
    client_secret_key: str = ""
    ddg_max_concurrent: int = 2
    ddg_min_interval: float = 1.5
    ddg_max_per_verify: int = 10

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
