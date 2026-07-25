from __future__ import annotations

import math
import re
from html import escape
from urllib.parse import parse_qs, urlparse

from src.core.youtube.models import YoutubeDownloadOption, YoutubeDownloadProgressSnapshot, YoutubeVideoPreview

_URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}
_TRAILING_PUNCTUATION = ").,!?:;]}>\"'"
_BYTES_IN_KIBIBYTE = 1024


def extract_youtube_url(text: str) -> str | None:
    for raw_match in _URL_PATTERN.findall(text):
        candidate = raw_match.rstrip(_TRAILING_PUNCTUATION)
        parsed_url = urlparse(candidate)
        host = parsed_url.netloc.lower()

        if host not in _YOUTUBE_HOSTS:
            continue

        if host.endswith("youtu.be") and parsed_url.path.strip("/"):
            return candidate

        if parsed_url.path == "/watch" and parse_qs(parsed_url.query).get("v"):
            return candidate

        if parsed_url.path.startswith("/shorts/") or parsed_url.path.startswith("/live/"):
            return candidate

    return None


def format_bytes(size_bytes: int | None) -> str:
    if size_bytes is None or size_bytes < 0:
        return "unknown"

    units = ("B", "KiB", "MiB", "GiB", "TiB")
    value = float(size_bytes)
    unit_index = 0

    while value >= _BYTES_IN_KIBIBYTE and unit_index < len(units) - 1:
        value /= _BYTES_IN_KIBIBYTE
        unit_index += 1

    if unit_index == 0:
        return f"{int(value)} {units[unit_index]}"

    return f"{value:.1f} {units[unit_index]}"


def format_duration(duration_seconds: int | None) -> str:
    if duration_seconds is None or duration_seconds < 0:
        return "unknown"

    hours, remainder = divmod(duration_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    return f"{minutes:02d}:{seconds:02d}"


def render_progress_bar(progress: float, *, width: int = 20) -> str:
    bounded_progress = max(0.0, min(1.0, progress))
    filled = min(width, math.floor(bounded_progress * width))
    empty = width - filled
    return f"[{'#' * filled}{'-' * empty}]"


def build_preview_caption(preview: YoutubeVideoPreview) -> str:
    duration = format_duration(preview.duration_seconds)
    uploader = escape(preview.uploader) if preview.uploader is not None else "unknown"
    title = escape(preview.title)

    return (
        "<b>🎬 YouTube Downloader</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"<b>📌 Title</b>\n{title}\n\n"
        f"<b>👤 Author:</b> {uploader}\n"
        f"<b>⏱ Duration:</b> {duration}\n"
        f"<b>🎞 Formats:</b> {len(preview.options)} available\n"
        "━━━━━━━━━━━━━━\n"
        "<i>👇 Choose the quality for download</i>"
    )


def build_no_uploadable_formats_caption(*, preview: YoutubeVideoPreview, upload_limit_bytes: int) -> str:
    duration = format_duration(preview.duration_seconds)
    uploader = escape(preview.uploader) if preview.uploader is not None else "unknown"
    title = escape(preview.title)

    return (
        "<b>⚠️ Video Is Too Large For Telegram</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"<b>📌 Title</b>\n{title}\n\n"
        f"<b>👤 Author:</b> {uploader}\n"
        f"<b>⏱ Duration:</b> {duration}\n"
        f"<b>📦 Telegram limit:</b> {format_bytes(upload_limit_bytes)}\n"
        "━━━━━━━━━━━━━━\n"
        "<i>No detected quality currently fits Telegram upload limits.</i>"
    )


def build_progress_caption(snapshot: YoutubeDownloadProgressSnapshot) -> str:
    total_bytes = snapshot.total_bytes or snapshot.downloaded_bytes or 0
    downloaded_bytes = snapshot.downloaded_bytes or 0
    progress = 0.0 if total_bytes == 0 else downloaded_bytes / total_bytes
    eta_text = format_duration(snapshot.eta_seconds)
    speed_text = format_bytes(int(snapshot.speed_bytes_per_second)) if snapshot.speed_bytes_per_second else "unknown"

    return (
        "<b>⬇️ Download In Progress</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"<code>{render_progress_bar(progress)} {progress * 100:05.1f}%</code>\n\n"
        f"<b>📦 Downloaded:</b> {format_bytes(downloaded_bytes)} / {format_bytes(snapshot.total_bytes)}\n"
        f"<b>⚡ Speed:</b> {speed_text}/s\n"
        f"<b>🕒 ETA:</b> {eta_text}"
    )


def build_result_caption(
    *,
    title: str,
    quality_label: str,
    duration_seconds: int | None,
    file_size_bytes: int,
    source_url: str,
) -> str:
    return (
        "<b>✅ Video Ready</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"<b>📌 Title</b>\n{escape(title)}\n\n"
        f"<b>🎞 Quality:</b> {escape(quality_label)}\n"
        f"<b>⏱ Duration:</b> {format_duration(duration_seconds)}\n"
        f"<b>💾 Size:</b> {format_bytes(file_size_bytes)}\n"
        f'<b>🔗 Source:</b> <a href="{escape(source_url)}">Open on YouTube</a>'
    )


def build_file_too_large_caption(
    *,
    title: str,
    quality: YoutubeDownloadOption,
    file_size_bytes: int,
    upload_limit_bytes: int,
) -> str:
    return (
        "<b>⚠️ Upload To Telegram Failed</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"<b>📌 Title</b>\n{escape(title)}\n\n"
        f"<b>🎞 Selected quality:</b> {escape(quality.label)}\n"
        f"<b>💾 Final size:</b> {format_bytes(file_size_bytes)}\n"
        f"<b>📦 Telegram limit:</b> {format_bytes(upload_limit_bytes)}\n"
        "━━━━━━━━━━━━━━\n"
        "<i>Try a smaller quality option.</i>"
    )


def build_youtube_auth_required_caption() -> str:
    return (
        "<b>🔐 YouTube Requires Authentication</b>\n"
        "━━━━━━━━━━━━━━\n"
        "YouTube asked to confirm that the downloader is not a bot.\n\n"
        "<b>Configure one of these options:</b>\n"
        "• <code>YOUTUBE_COOKIES_PATH</code> to a Netscape cookies file\n"
        "• <code>YOUTUBE_COOKIES_FROM_BROWSER</code> with your browser name\n\n"
        "<i>Example:</i> <code>YOUTUBE_COOKIES_FROM_BROWSER=chrome</code>"
    )


def build_youtube_browser_cookies_unsupported_caption() -> str:
    return (
        "<b>⚠️ Browser Cookies Are Not Available In The Container</b>\n"
        "━━━━━━━━━━━━━━\n"
        "The bot is running on Linux inside Docker, but your browser cookies live on the host OS.\n\n"
        "<b>Use this instead:</b>\n"
        "• export YouTube cookies to a Netscape cookies file\n"
        "• mount that file into the container\n"
        "• set <code>YOUTUBE_COOKIES_PATH</code> to that file path\n\n"
        "<b>Do not use</b> <code>YOUTUBE_COOKIES_FROM_BROWSER</code> inside this containerized setup."
    )
