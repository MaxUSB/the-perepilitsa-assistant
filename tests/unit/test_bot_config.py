from __future__ import annotations

import pytest
from pydantic import SecretStr
from pydantic_settings import SettingsConfigDict

from src.core.bot.config import BotConfig


class EnvOnlyBotConfig(BotConfig):
    model_config = SettingsConfigDict(extra="ignore", frozen=True)


def test_bot_config_parses_csv_allowed_user_ids() -> None:
    config = BotConfig.model_validate(
        {
            "BOT_TOKEN": SecretStr("token"),
            "BOT_ALLOWED_USER_IDS": "1, 2,3",
        }
    )

    assert config.allowed_user_ids == frozenset({1, 2, 3})


def test_bot_config_accepts_telegram_proxy_url() -> None:
    config = BotConfig.model_validate(
        {
            "BOT_TOKEN": SecretStr("token"),
            "BOT_ALLOWED_USER_IDS": "1",
            "BOT_TELEGRAM_PROXY_URL": "socks5://192.168.1.1:1081",
        }
    )

    assert config.telegram_proxy_url == "socks5://192.168.1.1:1081"


def test_bot_config_accepts_telegram_api_base_url() -> None:
    config = BotConfig.model_validate(
        {
            "BOT_TOKEN": SecretStr("token"),
            "BOT_ALLOWED_USER_IDS": "1",
            "BOT_TELEGRAM_API_BASE_URL": "http://telegram-bot-api:8081/",
        }
    )

    assert config.telegram_api_base_url == "http://telegram-bot-api:8081"


def test_bot_config_reads_csv_allowed_user_ids_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("BOT_ALLOWED_USER_IDS", "378866820,536880573")

    config = EnvOnlyBotConfig()

    assert config.allowed_user_ids == frozenset({378866820, 536880573})
