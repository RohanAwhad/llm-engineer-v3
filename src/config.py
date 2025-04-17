from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings loaded from environment variables or .env file."""

    # API keys
    LANGFUSE_PUBLIC_KEY: str
    LANGFUSE_SECRET_KEY: str

# Create settings instance
settings = Settings()

