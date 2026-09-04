import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest
from yt_dlp.utils import DownloadError

from src.core.youtube import YoutubeConfig
from src.core.youtube.client import YoutubeVideoUnavailableError
from src.core.youtube.models import YoutubeDownloadOption, YoutubeDownloadProgressSnapshot
from src.logic.youtube.client import YtDlpYoutubeClient, _build_download_options, _pick_downloaded_file

_EXPECTED_COMBINED_SIZE = 350
_COMPLETED_DOWNLOAD_BYTES = 100


def test_client_uses_supported_javascript_runtime_and_web_player(tmp_path: Path) -> None:
    config = YoutubeConfig.model_validate(
        {
            "download_dir": tmp_path,
            "cookies_path": None,
            "cookies_from_browser": None,
            "max_quality": 1080,
            "progress_update_interval_seconds": 1.5,
            "telegram_upload_limit_bytes": 2_000_000_000,
            "request_ttl_seconds": 3600,
        }
    )

    options = YtDlpYoutubeClient(config=config)._base_options(skip_download=False)

    assert options["js_runtimes"] == {"deno": {}}
    assert options["extractor_args"] == {"youtube": {"player_client": ["web_embedded"]}}


def test_client_converts_missing_formats_to_domain_error(tmp_path: Path) -> None:
    config = YoutubeConfig.model_validate(
        {
            "download_dir": tmp_path,
            "cookies_path": None,
            "cookies_from_browser": None,
            "max_quality": 1080,
            "progress_update_interval_seconds": 1.5,
            "telegram_upload_limit_bytes": 2_000_000_000,
            "request_ttl_seconds": 3600,
        }
    )
    client = YtDlpYoutubeClient(config=config)

    with pytest.raises(YoutubeVideoUnavailableError):
        client._raise_domain_error(DownloadError("Requested format is not available"))


def test_client_downloads_public_media_without_cookies_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = YoutubeConfig.model_validate(
        {
            "download_dir": tmp_path,
            "cookies_path": tmp_path / "cookies.txt",
            "cookies_from_browser": None,
            "max_quality": 1080,
            "progress_update_interval_seconds": 1.5,
            "telegram_upload_limit_bytes": 2_000_000_000,
            "request_ttl_seconds": 3600,
        }
    )
    client = YtDlpYoutubeClient(config=config)
    download_once = MagicMock(return_value=None)
    monkeypatch.setattr(client, "_download_video_once", download_once)
    request_dir = tmp_path / "request"
    request_dir.mkdir()
    (request_dir / "partial.mp4.part").write_bytes(b"partial")
    option = YoutubeDownloadOption(key="720p", label="720p", selector="136+140", container="mp4")

    client._download_video("https://youtu.be/example", option, request_dir, MagicMock())

    assert [call.kwargs["use_cookies"] for call in download_once.call_args_list] == [False]
    assert (request_dir / "partial.mp4.part").exists()


def test_client_retries_failed_public_download_with_configured_cookies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = YoutubeConfig.model_validate(
        {
            "download_dir": tmp_path,
            "cookies_path": tmp_path / "cookies.txt",
            "cookies_from_browser": None,
            "max_quality": 1080,
            "progress_update_interval_seconds": 1.5,
            "telegram_upload_limit_bytes": 2_000_000_000,
            "request_ttl_seconds": 3600,
        }
    )
    client = YtDlpYoutubeClient(config=config)
    download_once = MagicMock(side_effect=[DownloadError("public download failed"), None])
    monkeypatch.setattr(client, "_download_video_once", download_once)
    request_dir = tmp_path / "request"
    request_dir.mkdir()
    (request_dir / "partial.mp4.part").write_bytes(b"partial")

    client._download_video("https://youtu.be/example", MagicMock(), request_dir, MagicMock())

    assert [call.kwargs["use_cookies"] for call in download_once.call_args_list] == [False, True]
    assert not (request_dir / "partial.mp4.part").exists()


async def test_download_waits_for_latest_progress_callback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = YoutubeConfig.model_validate(
        {
            "download_dir": tmp_path,
            "cookies_path": None,
            "cookies_from_browser": None,
            "max_quality": 1080,
            "progress_update_interval_seconds": 1.5,
            "telegram_upload_limit_bytes": 2_000_000_000,
            "request_ttl_seconds": 3600,
        }
    )
    client = YtDlpYoutubeClient(config=config)
    received_bytes: list[int | None] = []

    def download_video(
        url: str,
        option: YoutubeDownloadOption,
        request_dir: Path,
        progress_hook: object,
    ) -> None:
        _ = url, option
        hook = cast(Callable[[dict[str, object]], None], progress_hook)
        hook({"status": "downloading", "downloaded_bytes": 10, "total_bytes": 100})
        hook({"status": "downloading", "downloaded_bytes": 100, "total_bytes": 100})
        (request_dir / "video.mp4").write_bytes(b"video")

    async def progress_callback(snapshot: YoutubeDownloadProgressSnapshot) -> None:
        await asyncio.sleep(0)
        received_bytes.append(snapshot.downloaded_bytes)

    monkeypatch.setattr(client, "_download_video", download_video)
    option = YoutubeDownloadOption(key="360p", label="360p", selector="18", container="mp4")

    result = await client.download(
        url="https://youtu.be/example",
        option=option,
        request_id="request",
        progress_callback=progress_callback,
    )

    assert received_bytes[-1] == _COMPLETED_DOWNLOAD_BYTES
    assert result.file_path.name == "video.mp4"


def test_pick_downloaded_file_finds_nested_output(tmp_path: Path) -> None:
    nested_dir = tmp_path / "nested" / "request"
    nested_dir.mkdir(parents=True)
    media_file = nested_dir / "video.mp4"
    media_file.write_bytes(b"video")

    result = _pick_downloaded_file(tmp_path)

    assert result == media_file


def test_pick_downloaded_file_ignores_partial_files(tmp_path: Path) -> None:
    (tmp_path / "video.mp4.part").write_bytes(b"partial")
    (tmp_path / "video.mp4.ytdl").write_bytes(b"state")

    result = _pick_downloaded_file(tmp_path)

    assert result is None


def test_build_download_options_uses_real_progressive_format_ids() -> None:
    metadata = {
        "formats": [
            {
                "format_id": "18",
                "height": 360,
                "filesize": 100,
                "vcodec": "avc1",
                "acodec": "mp4a",
                "ext": "mp4",
            },
            {
                "format_id": "22",
                "height": 720,
                "filesize": 200,
                "vcodec": "avc1",
                "acodec": "mp4a",
                "ext": "mp4",
            },
        ]
    }

    options = _build_download_options(metadata=metadata, max_quality=1080)

    assert [option.selector for option in options] == ["22", "18"]


def test_build_download_options_combines_real_video_and_audio_format_ids() -> None:
    metadata = {
        "formats": [
            {
                "format_id": "137",
                "height": 1080,
                "filesize": 300,
                "vcodec": "avc1",
                "acodec": "none",
                "ext": "mp4",
            },
            {
                "format_id": "399",
                "height": 1080,
                "filesize": 250,
                "vcodec": "vp9",
                "acodec": "none",
                "ext": "webm",
            },
            {
                "format_id": "140",
                "height": None,
                "filesize": 50,
                "vcodec": "none",
                "acodec": "mp4a",
                "ext": "m4a",
            },
        ]
    }

    options = _build_download_options(metadata=metadata, max_quality=1080)

    assert len(options) == 1
    assert options[0].selector == "137+140"
    assert options[0].estimated_size_bytes == _EXPECTED_COMBINED_SIZE


def test_build_download_options_prefers_original_audio_without_drc() -> None:
    metadata = {
        "formats": [
            {
                "format_id": "136",
                "height": 720,
                "filesize": 500,
                "vcodec": "avc1",
                "acodec": "none",
                "ext": "mp4",
            },
            {
                "format_id": "140-0",
                "height": None,
                "filesize": 102,
                "vcodec": "none",
                "acodec": "mp4a.40.2",
                "ext": "m4a",
                "language": "en-US",
                "language_preference": -1,
                "format_note": "English (US), medium",
                "abr": 129.5,
            },
            {
                "format_id": "140-drc",
                "height": None,
                "filesize": 101,
                "vcodec": "none",
                "acodec": "mp4a.40.2",
                "ext": "m4a",
                "language": "ru",
                "language_preference": 10,
                "format_note": "Russian original (default), medium, DRC",
                "abr": 129.5,
            },
            {
                "format_id": "140-1",
                "height": None,
                "filesize": 100,
                "vcodec": "none",
                "acodec": "mp4a.40.2",
                "ext": "m4a",
                "language": "ru",
                "language_preference": 10,
                "format_note": "Russian original (default), medium",
                "abr": 129.5,
            },
        ]
    }

    options = _build_download_options(metadata=metadata, max_quality=720)

    assert options[0].selector == "136+140-1"
