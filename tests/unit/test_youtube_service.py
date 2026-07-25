from __future__ import annotations

from src.core.bot.config import BotConfig
from src.core.youtube.client import YoutubeProgressCallback
from src.core.youtube.config import YoutubeConfig
from src.core.youtube.models import YoutubeDownloadOption, YoutubeDownloadResult, YoutubeVideoPreview
from src.logic.youtube.service import YoutubeService
from src.logic.youtube.store import YoutubeRequestStore


class DummyYoutubeClient:
    async def inspect(self, url: str) -> YoutubeVideoPreview:
        raise NotImplementedError

    async def download(
        self,
        *,
        url: str,
        option: YoutubeDownloadOption,
        request_id: str,
        progress_callback: YoutubeProgressCallback | None = None,
    ) -> YoutubeDownloadResult:
        raise NotImplementedError

    async def cleanup_request_files(self, request_id: str) -> None:
        _ = request_id


def test_filter_uploadable_options_removes_large_variants() -> None:
    service = YoutubeService(
        bot_config=BotConfig.model_validate(
            {
                "BOT_TOKEN": "token",
                "BOT_ALLOWED_USER_IDS": "1",
            }
        ),
        youtube_client=DummyYoutubeClient(),
        youtube_store=YoutubeRequestStore(request_ttl_seconds=60),
        youtube_config=YoutubeConfig.model_validate(
            {
                "YOUTUBE_TELEGRAM_UPLOAD_LIMIT_BYTES": 100,
            }
        ),
    )
    options = (
        YoutubeDownloadOption(
            key="small",
            label="360p mp4",
            selector="small",
            container="mp4",
            estimated_size_bytes=90,
        ),
        YoutubeDownloadOption(
            key="large",
            label="1080p mp4",
            selector="large",
            container="mp4",
            estimated_size_bytes=150,
        ),
        YoutubeDownloadOption(
            key="unknown",
            label="best mp4",
            selector="best",
            container="mp4",
            estimated_size_bytes=None,
        ),
    )

    filtered_options = service.filter_uploadable_options(options)

    assert tuple(option.key for option in filtered_options) == ("small", "unknown")
