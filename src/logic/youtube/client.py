import asyncio
import shutil
from collections.abc import Callable, Coroutine, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

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


class YoutubeAuthenticationRequiredError(Exception):
    pass


class YoutubeBrowserCookiesUnsupportedError(Exception):
    pass


class _YtDlpLogger:
    def debug(self, _message: str) -> None:
        return None

    def info(self, _message: str) -> None:
        return None

    def warning(self, _message: str) -> None:
        return None

    def error(self, _message: str) -> None:
        return None


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
        try:
            return self._extract_metadata_once(url=url, use_cookies=True)
        except DownloadError as error:
            if self._should_retry_metadata_without_cookies(error):
                return self._extract_metadata_once(url=url, use_cookies=False)
            raise

    def _extract_metadata_once(self, *, url: str, use_cookies: bool) -> dict[str, object]:
        youtube_dl_factory = cast(Any, YoutubeDL)
        youtube_dl = cast("YoutubeDLType", youtube_dl_factory(self._metadata_options(use_cookies=use_cookies)))
        try:
            with youtube_dl:
                extracted = youtube_dl.extract_info(url, download=False)
        except DownloadError as error:
            self._raise_if_authentication_required(error)
            raise
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
        try:
            with youtube_dl:
                youtube_dl.download([url])
        except DownloadError as error:
            self._raise_if_authentication_required(error)
            raise

    def _base_options(self, *, skip_download: bool, use_cookies: bool = True) -> dict[str, object]:
        download_dir = self._config.download_dir.resolve()
        options: dict[str, object] = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": skip_download,
            "paths": {"home": str(download_dir)},
            "logger": _YtDlpLogger(),
        }
        if use_cookies and self._config.cookies_path is not None:
            options["cookiefile"] = str(self._config.cookies_path.resolve())
        if use_cookies and self._config.cookies_from_browser is not None:
            options["cookiesfrombrowser"] = (self._config.cookies_from_browser,)
        return options

    def _metadata_options(self, *, use_cookies: bool) -> dict[str, object]:
        options = self._base_options(skip_download=True, use_cookies=use_cookies)
        options.update(
            {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
                "simulate": True,
                "format": None,
            }
        )
        return options

    def _resolve_request_dir(self, request_id: str) -> Path:
        return (self._config.download_dir / request_id).resolve()

    def _raise_if_authentication_required(self, error: DownloadError) -> None:
        error_message = str(error)
        if "unsupported platform: linux" in error_message and self._config.cookies_from_browser is not None:
            raise YoutubeBrowserCookiesUnsupportedError(error_message) from error

        if (
            "confirm you're not a bot" in error_message
            or "cookies-from-browser" in error_message
            or "--cookies" in error_message
        ):
            raise YoutubeAuthenticationRequiredError(error_message) from error

    def _should_retry_metadata_without_cookies(self, error: DownloadError) -> bool:
        if self._config.cookies_path is None and self._config.cookies_from_browser is None:
            return False

        error_message = str(error)
        return "Requested format is not available" in error_message


def _build_download_options(*, metadata: Mapping[str, object], max_quality: int) -> list[YoutubeDownloadOption]:
    raw_formats = metadata.get("formats")
    if not isinstance(raw_formats, list):
        return []

    audio_only_formats: list[tuple[str, int | None]] = []
    progressive_candidates: dict[int, YoutubeDownloadOption] = {}
    adaptive_candidates: dict[int, YoutubeDownloadOption] = {}

    for raw_format in raw_formats:
        parsed_format = _parse_download_format(raw_format=raw_format, max_quality=max_quality)
        if parsed_format is None:
            continue

        if parsed_format.kind == "audio":
            audio_only_formats.append((parsed_format.option.selector, parsed_format.option.estimated_size_bytes))
            continue

        option = parsed_format.option
        height = option.height
        if height is None:
            continue

        if parsed_format.kind == "progressive":
            existing_progressive = progressive_candidates.get(height)
            if existing_progressive is None or _is_better_option(option=option, other=existing_progressive):
                progressive_candidates[height] = option
            continue

        existing_adaptive = adaptive_candidates.get(height)
        if existing_adaptive is None or _is_better_option(option=option, other=existing_adaptive):
            adaptive_candidates[height] = option

    preferred_audio = _pick_preferred_audio_format(audio_only_formats)
    options: list[YoutubeDownloadOption] = []
    for height in sorted({*adaptive_candidates.keys(), *progressive_candidates.keys()}, reverse=True):
        progressive_option = progressive_candidates.get(height)
        if progressive_option is not None:
            options.append(progressive_option)
            continue

        adaptive_option = adaptive_candidates.get(height)
        if adaptive_option is None:
            continue

        options.append(_build_adaptive_download_option(option=adaptive_option, preferred_audio=preferred_audio))

    return options[:4]


def _pick_preferred_audio_format(audio_formats: list[tuple[str, int | None]]) -> tuple[str, int | None] | None:
    if not audio_formats:
        return None

    return max(audio_formats, key=lambda item: item[1] if item[1] is not None else -1)


def _is_better_option(*, option: YoutubeDownloadOption, other: YoutubeDownloadOption) -> bool:
    option_size = option.estimated_size_bytes if option.estimated_size_bytes is not None else -1
    other_size = other.estimated_size_bytes if other.estimated_size_bytes is not None else -1
    return option_size > other_size


def _build_adaptive_download_option(
    *,
    option: YoutubeDownloadOption,
    preferred_audio: tuple[str, int | None] | None,
) -> YoutubeDownloadOption:
    selector = option.selector
    estimated_size = option.estimated_size_bytes
    container = option.container

    if preferred_audio is not None:
        audio_format_id, audio_size_bytes = preferred_audio
        selector = f"{option.selector}+{audio_format_id}"
        container = "mp4"
        if estimated_size is not None and audio_size_bytes is not None:
            estimated_size += audio_size_bytes

    return option.model_copy(
        update={
            "selector": selector,
            "container": container,
            "estimated_size_bytes": estimated_size,
        }
    )


class _ParsedDownloadFormat:
    def __init__(self, *, kind: str, option: YoutubeDownloadOption) -> None:
        self.kind = kind
        self.option = option


def _parse_download_format(*, raw_format: object, max_quality: int) -> _ParsedDownloadFormat | None:
    if not isinstance(raw_format, Mapping):
        return None

    format_id = raw_format.get("format_id")
    if not isinstance(format_id, str) or not format_id:
        return None

    size_bytes = _coerce_int(raw_format.get("filesize") or raw_format.get("filesize_approx"))
    vcodec = str(raw_format.get("vcodec") or "none")
    acodec = str(raw_format.get("acodec") or "none")
    ext = str(raw_format.get("ext") or "mp4")

    if acodec != "none" and vcodec == "none":
        return _ParsedDownloadFormat(
            kind="audio",
            option=YoutubeDownloadOption(
                key=format_id,
                label=ext,
                selector=format_id,
                container=ext,
                estimated_size_bytes=size_bytes,
            ),
        )

    height = _coerce_int(raw_format.get("height"))
    if height is None or height > max_quality or vcodec == "none":
        return None

    return _ParsedDownloadFormat(
        kind="progressive" if acodec != "none" else "adaptive",
        option=YoutubeDownloadOption(
            key=f"{height}p",
            label=f"{height}p {ext}",
            selector=format_id,
            container=ext,
            height=height,
            estimated_size_bytes=size_bytes,
        ),
    )


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
