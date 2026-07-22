from __future__ import annotations

from dataclasses import dataclass

from src.core.app.config import AppConfig
from src.core.bot.config import BotConfig
from src.core.youtube.config import YoutubeConfig
from src.logic.youtube.client import YtDlpYoutubeClient
from src.logic.youtube.service import YoutubeService
from src.logic.youtube.store import YoutubeRequestStore


@dataclass(slots=True)
class ApplicationContext:
    app_config: AppConfig
    bot_config: BotConfig
    youtube_config: YoutubeConfig
    youtube_store: YoutubeRequestStore
    youtube_service: YoutubeService

    @classmethod
    def from_configs(
        cls,
        *,
        app_config: AppConfig,
        bot_config: BotConfig,
        youtube_config: YoutubeConfig,
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
        )
