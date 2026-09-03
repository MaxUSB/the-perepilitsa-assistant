from pathlib import Path

from src.logic.youtube.client import _build_download_options, _pick_downloaded_file

_EXPECTED_COMBINED_SIZE = 350


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
