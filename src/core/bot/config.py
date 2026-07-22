from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class BotConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    token: SecretStr = Field(default=SecretStr(""), validation_alias=AliasChoices("BOT_TOKEN"))
    allowed_user_ids: Annotated[frozenset[int], NoDecode] = Field(
        default=frozenset(),
        validation_alias=AliasChoices("BOT_ALLOWED_USER_IDS"),
    )
    delete_source_message: bool = Field(
        default=True,
        validation_alias=AliasChoices("BOT_DELETE_SOURCE_MESSAGE"),
    )
    telegram_proxy_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("BOT_TELEGRAM_PROXY_URL"),
    )

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def parse_allowed_user_ids(cls, value: object) -> frozenset[int]:
        if value is None:
            return frozenset()

        if isinstance(value, int):
            return frozenset({value})

        if isinstance(value, str):
            items = [item.strip() for item in value.split(",") if item.strip()]
            return frozenset(int(item) for item in items)

        if isinstance(value, Iterable):
            return frozenset(int(str(item).strip()) for item in value)

        msg = "BOT_ALLOWED_USER_IDS must be a CSV string or an iterable of integers"
        raise TypeError(msg)

    @field_validator("token")
    @classmethod
    def validate_token(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            msg = "BOT_TOKEN must be configured"
            raise ValueError(msg)

        return value

    @field_validator("allowed_user_ids")
    @classmethod
    def validate_allowed_user_ids(cls, value: frozenset[int]) -> frozenset[int]:
        if not value:
            msg = "At least one allowed Telegram user id must be configured"
            raise ValueError(msg)

        return value

    @field_validator("telegram_proxy_url")
    @classmethod
    def validate_telegram_proxy_url(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized_value = value.strip()
        if not normalized_value:
            return None

        if "://" not in normalized_value:
            msg = "BOT_TELEGRAM_PROXY_URL must include a scheme, for example socks5://192.168.1.1:1081"
            raise ValueError(msg)

        return normalized_value
