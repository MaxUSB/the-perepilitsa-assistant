from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        extra="ignore",
        frozen=True,
    )

    env: str = Field(default="dev")
    log_level: str = Field(default="INFO")
    runtime_dir: Path = Field(default=Path(".runtime"))
