import pytest
from pydantic import SecretStr
from pydantic_settings import SettingsConfigDict

from src.core.app import load_settings
from src.core.bot.config import BotConfig


class EnvOnlyBotConfig(BotConfig):
    model_config = SettingsConfigDict(env_prefix="BOT_", extra="ignore", frozen=True)


def bot_config_data(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "token": SecretStr("token"),
        "allowed_user_ids": "1",
        "delete_source_message": True,
        "telegram_proxy_url": None,
        "telegram_api_base_url": None,
    }
    data.update(overrides)
    return data


def test_bot_config_parses_csv_allowed_user_ids() -> None:
    config = BotConfig.model_validate(bot_config_data(allowed_user_ids="1, 2,3"))

    assert config.allowed_user_ids == frozenset({1, 2, 3})


def test_bot_config_accepts_telegram_proxy_url() -> None:
    config = BotConfig.model_validate(bot_config_data(telegram_proxy_url="socks5://192.168.1.1:1081"))

    assert config.telegram_proxy_url == "socks5://192.168.1.1:1081"


def test_bot_config_accepts_telegram_api_base_url() -> None:
    config = BotConfig.model_validate(bot_config_data(telegram_api_base_url="http://telegram-bot-api:8081/"))

    assert config.telegram_api_base_url == "http://telegram-bot-api:8081"


def test_bot_config_reads_csv_allowed_user_ids_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("BOT_ALLOWED_USER_IDS", "378866820,536880573")
    monkeypatch.setenv("BOT_DELETE_SOURCE_MESSAGE", "true")
    monkeypatch.setenv("BOT_TELEGRAM_PROXY_URL", "")
    monkeypatch.setenv("BOT_TELEGRAM_API_BASE_URL", "")

    config = load_settings(EnvOnlyBotConfig)

    assert config.allowed_user_ids == frozenset({378866820, 536880573})
