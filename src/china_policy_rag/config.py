"""Environment-based configuration with safe local defaults."""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration for local development and future provider integrations."""

    model_config = SettingsConfigDict(
        env_prefix="CHINA_POLICY_RAG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    raw_data_dir: Path = Path("data/raw")
    processed_data_dir: Path = Path("data/processed")
    ingestion_manifest_path: Path = Path("data/raw/manifest.yaml")
    database_url: str | None = None
    embedding_provider: str | None = None
    llm_provider: str | None = None
    embedding_api_key: SecretStr | None = None
    llm_api_key: SecretStr | None = None
