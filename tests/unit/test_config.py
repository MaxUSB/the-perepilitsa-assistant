from pathlib import Path

import pytest
from pydantic_settings import SettingsConfigDict

from src.core.app import AppConfig, load_settings
from src.core.bot import BotConfig
from src.core.gpn import GpnConfig
from src.core.youtube import YoutubeConfig

_MAX_QUALITY = 1080


class EnvOnlyAppConfig(AppConfig):
    model_config = SettingsConfigDict(env_prefix="APP_", extra="ignore", frozen=True)


class EnvOnlyYoutubeConfig(YoutubeConfig):
    model_config = SettingsConfigDict(env_prefix="YOUTUBE_", extra="ignore", frozen=True)


class EnvOnlyGpnConfig(GpnConfig):
    model_config = SettingsConfigDict(env_prefix="GPN_", extra="ignore", frozen=True)


@pytest.mark.parametrize("config_type", [AppConfig, BotConfig, YoutubeConfig, GpnConfig])
def test_configs_have_no_field_defaults(config_type: type[AppConfig | BotConfig | YoutubeConfig | GpnConfig]) -> None:
    assert all(field.is_required() for field in config_type.model_fields.values())


def test_app_config_loads_prefixed_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("APP_RUNTIME_DIR", "~/runtime")

    config = load_settings(EnvOnlyAppConfig)

    assert config.env == "test"
    assert config.log_level == "DEBUG"
    assert config.runtime_dir == Path("~/runtime")


def test_youtube_config_loads_prefixed_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {
        "YOUTUBE_DOWNLOAD_DIR": "~/downloads",
        "YOUTUBE_COOKIES_PATH": "",
        "YOUTUBE_COOKIES_FROM_BROWSER": "",
        "YOUTUBE_MAX_QUALITY": "1080",
        "YOUTUBE_PROGRESS_UPDATE_INTERVAL_SECONDS": "1.5",
        "YOUTUBE_TELEGRAM_UPLOAD_LIMIT_BYTES": "1000",
        "YOUTUBE_REQUEST_TTL_SECONDS": "60",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    config = load_settings(EnvOnlyYoutubeConfig)

    assert config.download_dir == Path("~/downloads").expanduser()
    assert config.cookies_path is None
    assert config.cookies_from_browser is None
    assert config.max_quality == _MAX_QUALITY


def test_gpn_config_loads_prefixed_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {
        "GPN_URL": "https://example.com",
        "GPN_CITY": " Тюмень ",
        "GPN_INTERVAL_SECONDS": "60",
        "GPN_REQUEST_TIMEOUT_SECONDS": "30",
        "GPN_RECIPIENT_IDS": "1,2",
        "GPN_STATE_PATH": "~/gpn-state.json",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    config = load_settings(EnvOnlyGpnConfig)

    assert config.city == "Тюмень"
    assert config.recipient_ids == frozenset({1, 2})
    assert config.state_path == Path("~/gpn-state.json").expanduser()
