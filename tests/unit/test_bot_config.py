from __future__ import annotations

from pydantic import SecretStr

from src.core.bot.config import BotConfig


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
