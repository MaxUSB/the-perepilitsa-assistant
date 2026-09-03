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
                "token": "token",
                "allowed_user_ids": "1",
                "delete_source_message": True,
                "telegram_proxy_url": None,
                "telegram_api_base_url": None,
            }
        ),
        youtube_client=DummyYoutubeClient(),
        youtube_store=YoutubeRequestStore(request_ttl_seconds=60),
        youtube_config=YoutubeConfig.model_validate(
            {
                "download_dir": ".runtime/youtube",
                "cookies_path": None,
                "cookies_from_browser": None,
                "max_quality": 1080,
                "progress_update_interval_seconds": 1.5,
                "telegram_upload_limit_bytes": 100,
                "request_ttl_seconds": 3600,
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
