from collections.abc import Awaitable, Callable
from typing import Protocol

from src.core.youtube.models import (
    YoutubeDownloadOption,
    YoutubeDownloadProgressSnapshot,
    YoutubeDownloadResult,
    YoutubeVideoPreview,
)

type YoutubeProgressCallback = Callable[[YoutubeDownloadProgressSnapshot], Awaitable[None]]


class YoutubeClient(Protocol):
    async def inspect(self, url: str) -> YoutubeVideoPreview: ...

    async def download(
        self,
        *,
        url: str,
        option: YoutubeDownloadOption,
        request_id: str,
        progress_callback: YoutubeProgressCallback | None = None,
    ) -> YoutubeDownloadResult: ...

    async def cleanup_request_files(self, request_id: str) -> None: ...
