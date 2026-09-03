from typing import Annotated

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from src.core.config import parse_int_set


class BotConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BOT_",
        extra="ignore",
        frozen=True,
    )

    token: SecretStr
    allowed_user_ids: Annotated[frozenset[int], NoDecode]
    delete_source_message: bool
    telegram_proxy_url: str | None
    telegram_api_base_url: str | None

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def parse_allowed_user_ids(cls, value: object) -> frozenset[int]:
        return parse_int_set(value, variable_name="BOT_ALLOWED_USER_IDS")

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

    @field_validator("telegram_api_base_url")
    @classmethod
    def validate_telegram_api_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized_value = value.strip().rstrip("/")
        if not normalized_value:
            return None

        if not normalized_value.startswith(("http://", "https://")):
            msg = "BOT_TELEGRAM_API_BASE_URL must start with http:// or https://"
            raise ValueError(msg)

        return normalized_value
