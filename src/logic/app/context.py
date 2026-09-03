from __future__ import annotations

from dataclasses import dataclass

from src.core.app.config import AppConfig
from src.core.bot.config import BotConfig
from src.core.gpn import GpnConfig
from src.core.youtube import YoutubeConfig
from src.logic.youtube import YoutubeRequestStore, YoutubeService, YtDlpYoutubeClient


@dataclass(slots=True)
class ApplicationContext:
    app_config: AppConfig

    bot_config: BotConfig

    youtube_config: YoutubeConfig
    youtube_store: YoutubeRequestStore
    youtube_service: YoutubeService

    gpn_config: GpnConfig

    @classmethod
    def from_configs(
        cls,
        *,
        app_config: AppConfig,
        bot_config: BotConfig,
        youtube_config: YoutubeConfig,
        gpn_config: GpnConfig,
    ) -> ApplicationContext:
        youtube_store = YoutubeRequestStore(request_ttl_seconds=youtube_config.request_ttl_seconds)
        youtube_client = YtDlpYoutubeClient(config=youtube_config)
        youtube_service = YoutubeService(
            bot_config=bot_config,
            youtube_client=youtube_client,
            youtube_store=youtube_store,
            youtube_config=youtube_config,
        )
        return cls(
            app_config=app_config,
            bot_config=bot_config,
            youtube_config=youtube_config,
            youtube_store=youtube_store,
            youtube_service=youtube_service,
            gpn_config=gpn_config,
        )
