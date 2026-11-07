
from pathlib import Path
from pydantic import Field,SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# Locate the root NEUROCORE project directory
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """
    Central configuration manager for NEUROCORE.
    """
    file_analysis_agent_key: SecretStr = SecretStr("")
    planning_agent_key: SecretStr = SecretStr("")
    verification_agent_key: SecretStr = SecretStr("")
    app_name: str = "NEUROCORE"
    app_version: str = "0.1.0"
    environment: str = "development"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"

    log_level: str = "INFO"
    database_path: Path = PROJECT_ROOT / "data" / "neurocore.db"
    memory_retention_min_age_days: int = Field(default=90, ge=1)
    memory_retention_inactivity_days: int = Field(default=90, ge=1)
    memory_automatic_archival_enabled: bool = False
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    allowed_scan_roots: list[str] = Field(default_factory=list)

# Shared application settings
settings = Settings()
