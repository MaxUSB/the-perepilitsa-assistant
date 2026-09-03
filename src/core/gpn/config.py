from collections.abc import Iterable
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GpnConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    url: str | None = Field(
        validation_alias=AliasChoices("GPN_URL"),
    )
    city: str = Field(validation_alias=AliasChoices("GPN_CITY"))
    interval_seconds: float = Field(
        gt=0,
        validation_alias=AliasChoices("GPN_INTERVAL_SECONDS"),
    )
    request_timeout_seconds: float = Field(
        gt=0,
        validation_alias=AliasChoices("GPN_REQUEST_TIMEOUT_SECONDS"),
    )
    recipient_ids: frozenset[int] = Field(
        validation_alias=AliasChoices("GPN_RECIPIENT_IDS"),
    )
    state_path: Path = Field(
        default=Path(".runtime/gpn/state.json"),
        validation_alias=AliasChoices("GPN_STATE_PATH"),
    )

    @field_validator("state_path", mode="before")
    @classmethod
    def expand_state_path(cls, value: object) -> Path:
        return Path(str(value)).expanduser()

    @field_validator("url")
    @classmethod
    def normalize_url(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized_value = value.strip()
        if not normalized_value:
            return None

        if not normalized_value.startswith(("http://", "https://")):
            msg = "GPN_URL must start with http:// or https://"
            raise ValueError(msg)

        return normalized_value

    @field_validator("city")
    @classmethod
    def normalize_city(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            msg = "GPN_CITY must not be empty"
            raise ValueError(msg)
        return normalized_value

    @field_validator("recipient_ids", mode="before")
    @classmethod
    def parse_recipient_ids(cls, value: object) -> frozenset[int]:
        if value is None:
            return frozenset()

        if isinstance(value, int):
            return frozenset({value})

        if isinstance(value, str):
            items = [item.strip() for item in value.split(",") if item.strip()]
            return frozenset(int(item) for item in items)

        if isinstance(value, Iterable):
            return frozenset(int(str(item).strip()) for item in value)

        msg = "GPN_RECIPIENT_IDS must be a CSV string or an iterable of integers"
        raise TypeError(msg)
