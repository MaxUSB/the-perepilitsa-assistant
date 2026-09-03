from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from src.core.config import parse_int_set


class GpnConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="GPN_",
        extra="ignore",
        frozen=True,
    )

    url: str | None
    city: str
    interval_seconds: float = Field(gt=0)
    request_timeout_seconds: float = Field(gt=0)
    recipient_ids: Annotated[frozenset[int], NoDecode]
    state_path: Path

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
        return parse_int_set(value, variable_name="GPN_RECIPIENT_IDS")
