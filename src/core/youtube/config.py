from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class YoutubeConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    download_dir: Path = Field(
        default=Path(".runtime/youtube"),
        validation_alias=AliasChoices("YOUTUBE_DOWNLOAD_DIR"),
    )
    cookies_path: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("YOUTUBE_COOKIES_PATH"),
    )
    cookies_from_browser: str | None = Field(
        default=None,
        validation_alias=AliasChoices("YOUTUBE_COOKIES_FROM_BROWSER"),
    )
    max_quality: int = Field(default=1080, validation_alias=AliasChoices("YOUTUBE_MAX_QUALITY"))
    progress_update_interval_seconds: float = Field(
        default=1.5,
        validation_alias=AliasChoices("YOUTUBE_PROGRESS_UPDATE_INTERVAL_SECONDS"),
    )
    telegram_upload_limit_bytes: int = Field(
        default=2_000_000_000,
        validation_alias=AliasChoices("YOUTUBE_TELEGRAM_UPLOAD_LIMIT_BYTES"),
    )
    request_ttl_seconds: int = Field(
        default=3600,
        validation_alias=AliasChoices("YOUTUBE_REQUEST_TTL_SECONDS"),
    )

    @field_validator("download_dir", "cookies_path", mode="before")
    @classmethod
    def expand_paths(cls, value: object) -> object:
        if value is None:
            return None

        return Path(str(value)).expanduser()

    @field_validator("cookies_from_browser")
    @classmethod
    def normalize_cookies_from_browser(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None
