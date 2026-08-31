from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    APP_NAME: str = "ExamGuard Pro"
    SECRET_KEY: str = "change-this-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    DATABASE_URL: str = "sqlite+aiosqlite:///./examguard_prod.db"
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40
    DB_POOL_TIMEOUT: int = 30
    CORS_ORIGINS: list[str] = ["*"]
    ALLOWED_IP_RANGES: str = "127.0.0.1/32,::1/128"
    REPORTS_DIR: Path = PROJECT_DIR / "reports"

    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = ""
    SMTP_USE_SSL: bool = False
    SMTP_STARTTLS: bool = True
    SMTP_TIMEOUT_SECONDS: int = 20
    FRONTEND_EXAM_URL: str = "http://127.0.0.1:8000/frontend/src/pages/exam.html"
    EXAM_INVITE_EXPIRE_HOURS: int = 72

    PISTON_API_URL: str = "https://emkc.org/api/v2/piston/execute"
    PISTON_API_TOKEN: str = ""
    PISTON_AUTH_HEADER: str = "Authorization"
    PISTON_AUTH_SCHEME: str = "Bearer"
    PISTON_COMPILE_TIMEOUT_MS: int = 10_000
    PISTON_RUN_TIMEOUT_MS: int = 3_000
    PISTON_MAX_CONCURRENT_EXECUTIONS: int = 20
    LOCAL_CODE_EXECUTION_FALLBACK: bool = True
    AUTO_SUBMIT_GRACE_SECONDS: int = 60
    DEFAULT_CONTEST_TITLE: str = "ExamGuard Pro Coding Contest"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-flash-latest"
    GEMINI_TIMEOUT_SECONDS: int = 90
    GEMINI_REMOTE_ENABLED: bool = True

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
