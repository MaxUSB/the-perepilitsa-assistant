from __future__ import annotations

import asyncio
import shutil
from collections.abc import Callable, Coroutine, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from yt_dlp import YoutubeDL

from src.core.youtube.client import YoutubeProgressCallback
from src.core.youtube.config import YoutubeConfig
from src.core.youtube.models import (
    YoutubeDownloadOption,
    YoutubeDownloadProgressSnapshot,
    YoutubeDownloadResult,
    YoutubeVideoPreview,
)

if TYPE_CHECKING:
    from yt_dlp import YoutubeDL as YoutubeDLType


class YtDlpYoutubeClient:
    def __init__(self, *, config: YoutubeConfig) -> None:
        self._config = config

    async def inspect(self, url: str) -> YoutubeVideoPreview:
        metadata = await asyncio.to_thread(self._extract_metadata, url)
        options = _build_download_options(metadata=metadata, max_quality=self._config.max_quality)
        if not options:
            msg = "No downloadable video formats were found for this URL"
            raise ValueError(msg)

        thumbnail_value = metadata.get("thumbnail")
        thumbnail_url = str(thumbnail_value) if isinstance(thumbnail_value, str) and thumbnail_value else None
        title = str(metadata.get("title") or "Unknown title")
        duration = _coerce_int(metadata.get("duration"))
        uploader = metadata.get("uploader")

        return YoutubeVideoPreview(
            source_url=url,
            title=title,
            thumbnail_url=thumbnail_url,
            duration_seconds=duration,
            uploader=str(uploader) if isinstance(uploader, str) else None,
            options=tuple(options),
        )

    async def download(
        self,
        *,
        url: str,
        option: YoutubeDownloadOption,
        request_id: str,
        progress_callback: YoutubeProgressCallback | None = None,
    ) -> YoutubeDownloadResult:
        loop = asyncio.get_running_loop()
        request_dir = self._resolve_request_dir(request_id)
        request_dir.mkdir(parents=True, exist_ok=True)

        def sync_progress_hook(payload: Mapping[str, object]) -> None:
            callback = progress_callback
            if callback is None:
                return

            snapshot = YoutubeDownloadProgressSnapshot(
                status=str(payload.get("status") or "unknown"),
                downloaded_bytes=_coerce_int(payload.get("downloaded_bytes")),
                total_bytes=_coerce_int(payload.get("total_bytes") or payload.get("total_bytes_estimate")),
                speed_bytes_per_second=_coerce_float(payload.get("speed")),
                eta_seconds=_coerce_int(payload.get("eta")),
                filename=str(payload.get("filename")) if payload.get("filename") is not None else None,
            )

            def schedule_progress_update(update_snapshot: YoutubeDownloadProgressSnapshot) -> None:
                coroutine = cast(Coroutine[Any, Any, None], callback(update_snapshot))
                progress_task: asyncio.Task[None] = asyncio.create_task(coroutine)
                _ = progress_task

            loop.call_soon_threadsafe(schedule_progress_update, snapshot)

        await asyncio.to_thread(
            self._download_video,
            url,
            option,
            request_dir,
            sync_progress_hook,
        )
        result_file = _pick_downloaded_file(request_dir)
        if result_file is None:
            msg = "yt-dlp finished without a resulting media file"
            raise FileNotFoundError(msg)

        return YoutubeDownloadResult(
            file_path=result_file,
            title=result_file.stem,
            source_url=url,
            selected_option=option,
            file_size_bytes=result_file.stat().st_size,
        )

    async def cleanup_request_files(self, request_id: str) -> None:
        request_dir = self._resolve_request_dir(request_id)
        if request_dir.exists():
            await asyncio.to_thread(shutil.rmtree, request_dir, ignore_errors=True)

    def _extract_metadata(self, url: str) -> dict[str, object]:
        youtube_dl_factory = cast(Any, YoutubeDL)
        youtube_dl = cast("YoutubeDLType", youtube_dl_factory(self._base_options(skip_download=True)))
        with youtube_dl:
            extracted = youtube_dl.extract_info(url, download=False)
        return cast(dict[str, object], extracted)

    def _download_video(
        self,
        url: str,
        option: YoutubeDownloadOption,
        request_dir: Path,
        progress_hook: Callable[[Mapping[str, object]], None],
    ) -> None:
        options = self._base_options(skip_download=False)
        options.update(
            {
                "format": option.selector,
                "outtmpl": str((request_dir / "%(title).180B-%(id)s.%(ext)s").resolve()),
                "merge_output_format": option.container,
                "progress_hooks": [progress_hook],
            }
        )
        youtube_dl_factory = cast(Any, YoutubeDL)
        youtube_dl = cast("YoutubeDLType", youtube_dl_factory(options))
        with youtube_dl:
            youtube_dl.download([url])

    def _base_options(self, *, skip_download: bool) -> dict[str, object]:
        download_dir = self._config.download_dir.resolve()
        options: dict[str, object] = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": skip_download,
            "paths": {"home": str(download_dir)},
        }
        if self._config.cookies_path is not None:
            options["cookiefile"] = str(self._config.cookies_path.resolve())
        return options

    def _resolve_request_dir(self, request_id: str) -> Path:
        return (self._config.download_dir / request_id).resolve()


def _build_download_options(*, metadata: Mapping[str, object], max_quality: int) -> list[YoutubeDownloadOption]:
    raw_formats = metadata.get("formats")
    if not isinstance(raw_formats, list):
        return []

    audio_sizes: list[int] = []
    video_candidates: dict[int, int] = {}
    progressive_candidates: dict[int, int] = {}

    for raw_format in raw_formats:
        if not isinstance(raw_format, Mapping):
            continue

        height = _coerce_int(raw_format.get("height"))
        if height is None or height > max_quality:
            continue

        size_bytes = _coerce_int(raw_format.get("filesize") or raw_format.get("filesize_approx"))
        vcodec = str(raw_format.get("vcodec") or "none")
        acodec = str(raw_format.get("acodec") or "none")
        ext = str(raw_format.get("ext") or "mp4")

        if acodec != "none" and vcodec == "none" and size_bytes is not None:
            audio_sizes.append(size_bytes)
            continue

        if vcodec == "none":
            continue

        if acodec != "none" and ext == "mp4" and size_bytes is not None:
            progressive_candidates[height] = max(progressive_candidates.get(height, 0), size_bytes)

        if size_bytes is not None:
            video_candidates[height] = max(video_candidates.get(height, 0), size_bytes)

    estimated_audio_size = max(audio_sizes) if audio_sizes else None
    options: list[YoutubeDownloadOption] = []
    for height in sorted({*video_candidates.keys(), *progressive_candidates.keys()}, reverse=True):
        progressive_size = progressive_candidates.get(height)
        if progressive_size is not None:
            options.append(
                YoutubeDownloadOption(
                    key=f"{height}p",
                    label=f"{height}p mp4",
                    selector=f"best[height<={height}][ext=mp4]/best[height<={height}]",
                    container="mp4",
                    height=height,
                    estimated_size_bytes=progressive_size,
                )
            )
            continue

        estimated_size = video_candidates.get(height)
        if estimated_size is not None and estimated_audio_size is not None:
            estimated_size += estimated_audio_size

        options.append(
            YoutubeDownloadOption(
                key=f"{height}p",
                label=f"{height}p mp4",
                selector=(
                    f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]"
                    f"/best[height<={height}][ext=mp4]/best[height<={height}]"
                ),
                container="mp4",
                height=height,
                estimated_size_bytes=estimated_size,
            )
        )

    return options[:4]


def _coerce_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _coerce_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, float):
        return value
    if isinstance(value, int):
        return float(value)
    return None


def _pick_downloaded_file(request_dir: Path) -> Path | None:
    if not request_dir.exists():
        return None

    files = [
        file_path
        for file_path in request_dir.rglob("*")
        if file_path.is_file() and file_path.suffix not in {".part", ".ytdl"}
    ]
    if not files:
        return None

    return max(files, key=lambda file_path: file_path.stat().st_size)
