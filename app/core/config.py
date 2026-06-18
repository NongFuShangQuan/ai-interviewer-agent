"""AI Interview Agent System - Core Configuration"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    app_name: str = "AI Interview Agent System"
    app_version: str = "1.0.0"
    debug: bool = True

    # LLM Configuration
    llm_api_key: str = ""
    llm_api_base_url: str = "https://api.siliconflow.cn/v1"
    llm_model: str = "mimo-v2-omni"

    # Database
    database_url: str = "sqlite+aiosqlite:///./ai_interview.db"

    # Server
    host: str = "0.0.0.0"
    port: int = 9000
    secret_key: str = "change-this-to-a-random-secret-key"

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "AI Interview <noreply@example.com>"

    # Interview
    interview_rounds: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
