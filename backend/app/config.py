from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    lm_studio_url: str = "http://localhost:1234/v1"
    lm_studio_api_key: str = "lm-studio"
    model_name: str = ""
    sec_api_url: str = "https://gwwso2.sec.gov.ph/companyinformationlookup/1.0.0"
    sec_api_key: str = ""

    model_config = {"env_file": os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"), "env_file_encoding": "utf-8"}


settings = Settings()
