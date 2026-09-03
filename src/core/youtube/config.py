from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class YoutubeConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="YOUTUBE_",
        extra="ignore",
        frozen=True,
    )

    download_dir: Path
    cookies_path: Path | None
    cookies_from_browser: str | None
    max_quality: int = Field(gt=0)
    progress_update_interval_seconds: float = Field(gt=0)
    telegram_upload_limit_bytes: int = Field(gt=0)
    request_ttl_seconds: int = Field(gt=0)

    @field_validator("download_dir", mode="before")
    @classmethod
    def expand_download_dir(cls, value: object) -> Path:
        return Path(str(value)).expanduser()

    @field_validator("cookies_path", mode="before")
    @classmethod
    def expand_optional_path(cls, value: object) -> Path | None:
        if value is None or not str(value).strip():
            return None
        return Path(str(value)).expanduser()

    @field_validator("cookies_from_browser")
    @classmethod
    def normalize_cookies_from_browser(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None
