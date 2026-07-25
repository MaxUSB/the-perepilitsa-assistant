from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class YoutubeDownloadOption(BaseModel):
    key: str
    label: str
    selector: str
    container: str
    height: int | None = None
    estimated_size_bytes: int | None = None


class YoutubeVideoPreview(BaseModel):
    source_url: str
    title: str
    thumbnail_url: str | None = None
    duration_seconds: int | None = None
    uploader: str | None = None
    options: tuple[YoutubeDownloadOption, ...]


class YoutubeDownloadRequest(BaseModel):
    request_id: str
    user_id: int
    chat_id: int
    source_message_id: int
    preview_message_id: int | None = None
    preview: YoutubeVideoPreview
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class YoutubeDownloadProgressSnapshot(BaseModel):
    status: str
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed_bytes_per_second: float | None = None
    eta_seconds: int | None = None
    filename: str | None = None
    phase: str = "download"


class YoutubeDownloadResult(BaseModel):
    file_path: Path
    title: str
    source_url: str
    selected_option: YoutubeDownloadOption
    duration_seconds: int | None = None
    file_size_bytes: int
