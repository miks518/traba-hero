from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    ai_api_key: str = ""
    ai_api_url: str = ""
    openrouter_api_key: str = ""
    openai_api_key: str = ""
    lm_studio_url: str = "http://localhost:1234/v1"
    lm_studio_api_key: str = "lm-studio"
    model_name: str = ""
    ai_temperature: float = 0.2
    ai_top_p: float = 1.0
    ai_max_tokens: int = 2048
    send_system_prompt: bool = True
    sec_api_url: str = "https://gwwso2.sec.gov.ph/companyinformationlookup/1.0.0"
    sec_api_key: str = ""
    google_search_api_key: str = ""
    google_search_cx: str = ""

    @property
    def effective_ai_api_key(self) -> str:
        for key in (self.ai_api_key, self.openrouter_api_key, self.openai_api_key, self.lm_studio_api_key):
            if key and key.strip():
                return key.strip()
        return "lm-studio"

    @property
    def effective_ai_url(self) -> str:
        if self.ai_api_url and self.ai_api_url.strip():
            return self.ai_api_url.strip()
        if self.lm_studio_url and self.lm_studio_url.strip():
            return self.lm_studio_url.strip()
        return "http://localhost:1234/v1"

    model_config = {
        "env_file": os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
