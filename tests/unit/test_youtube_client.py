from __future__ import annotations

from pathlib import Path

from src.logic.youtube.client import _pick_downloaded_file


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
