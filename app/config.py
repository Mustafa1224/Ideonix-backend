import os

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


class Settings:
    app_env: str = os.getenv("APP_ENV", "development").lower()  # set APP_ENV=production when deployed
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./ideonix.db")
    jwt_secret: str = os.getenv("JWT_SECRET", "")
    jwt_expire_minutes: int = _int("JWT_EXPIRE_MINUTES", 1440)
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    cors_origins: list[str] = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

    # AI providers: each is used only when its key AND model are set; tried in this order.
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "")
    gemini_fallback_model: str = os.getenv("GEMINI_FALLBACK_MODEL", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "")
    router_api_key: str = os.getenv("ROUTER_API_KEY", "")
    router_base_url: str = os.getenv("ROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    router_model: str = os.getenv("ROUTER_MODEL", "")

    # abuse protection
    auth_attempts_per_minute: int = _int("AUTH_ATTEMPTS_PER_MINUTE", 10)
    analyses_per_hour: int = _int("ANALYSES_PER_HOUR", 20)
    max_running_per_user: int = _int("MAX_RUNNING_PER_USER", 2)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def ai_providers(self) -> list[str]:
        out = []
        if self.gemini_api_key and self.gemini_model:
            out.append("gemini")
        if self.openai_api_key and self.openai_model:
            out.append("openai")
        if self.router_api_key and self.router_model:
            out.append("router")
        return out

    def validate(self) -> None:
        """Refuse to start with an unsafe or incomplete configuration."""
        problems = []
        if len(self.jwt_secret) < 32:
            problems.append("JWT_SECRET must be set to a random string of at least 32 characters")
        if not self.ai_providers():
            problems.append("no AI provider configured: set GEMINI_API_KEY and GEMINI_MODEL (or OpenAI/router keys) in .env")
        if self.is_production and not self.cors_origins:
            problems.append("CORS_ORIGINS must list your website address in production")
        if self.is_production and self.database_url.startswith("sqlite"):
            problems.append("use PostgreSQL (DATABASE_URL) in production; SQLite files are lost on most hosts")
        if problems:
            raise RuntimeError("Invalid configuration: " + "; ".join(problems))


settings = Settings()