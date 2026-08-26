from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    mongodb_uri: str | None = None
    mongodb_database: str = "loan_verification_copilot"
    jwt_secret: str = "development-only-change-me"
    jwt_expiry_minutes: int = 480
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    cors_origins: str = "http://localhost:5173"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
@lru_cache
def get_settings() -> Settings: return Settings()
