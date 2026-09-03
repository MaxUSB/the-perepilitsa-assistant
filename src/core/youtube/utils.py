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
        return "неизвестно"

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
        return "неизвестно"

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
    uploader = escape(preview.uploader) if preview.uploader is not None else "неизвестен"
    title = escape(preview.title)

    return (
        "<b>🎬 Скачивание с YouTube</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"<b>📌 Название</b>\n{title}\n\n"
        f"<b>👤 Автор:</b> {uploader}\n"
        f"<b>⏱ Длительность:</b> {duration}\n"
        f"<b>🎞 Доступно вариантов:</b> {len(preview.options)}\n"
        "━━━━━━━━━━━━━━\n"
        "<i>👇 Выберите качество для скачивания</i>"
    )


def build_no_uploadable_formats_caption(*, preview: YoutubeVideoPreview, upload_limit_bytes: int) -> str:
    duration = format_duration(preview.duration_seconds)
    uploader = escape(preview.uploader) if preview.uploader is not None else "неизвестен"
    title = escape(preview.title)

    return (
        "<b>⚠️ Видео слишком большое для Telegram</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"<b>📌 Название</b>\n{title}\n\n"
        f"<b>👤 Автор:</b> {uploader}\n"
        f"<b>⏱ Длительность:</b> {duration}\n"
        f"<b>📦 Лимит Telegram:</b> {format_bytes(upload_limit_bytes)}\n"
        "━━━━━━━━━━━━━━\n"
        "<i>Ни один доступный вариант качества не помещается в лимит Telegram.</i>"
    )


def build_progress_caption(snapshot: YoutubeDownloadProgressSnapshot) -> str:
    total_bytes = snapshot.total_bytes or snapshot.downloaded_bytes or 0
    downloaded_bytes = snapshot.downloaded_bytes or 0
    progress = min(1.0, max(0.0, 0.0 if total_bytes == 0 else downloaded_bytes / total_bytes))
    eta_text = format_duration(snapshot.eta_seconds)
    speed_text = format_bytes(int(snapshot.speed_bytes_per_second)) if snapshot.speed_bytes_per_second else "неизвестно"
    if snapshot.phase == "upload":
        return (
            "<b>📤 Загрузка в Telegram</b>\n"
            "━━━━━━━━━━━━━━\n"
            f"<code>{render_progress_bar(progress)} {progress * 100:05.1f}%</code>\n\n"
            f"<b>📦 Загружено:</b> {format_bytes(downloaded_bytes)} / {format_bytes(snapshot.total_bytes)}\n"
            "<i>Telegram принимает файл...</i>"
        )

    return (
        "<b>⬇️ Скачивание видео</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"<code>{render_progress_bar(progress)} {progress * 100:05.1f}%</code>\n\n"
        f"<b>📦 Скачано:</b> {format_bytes(downloaded_bytes)} / {format_bytes(snapshot.total_bytes)}\n"
        f"<b>⚡ Скорость:</b> {speed_text}/с\n"
        f"<b>🕒 Осталось:</b> {eta_text}"
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
        "<b>✅ Видео готово</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"<b>📌 Название</b>\n{escape(title)}\n\n"
        f"<b>🎞 Качество:</b> {escape(quality_label)}\n"
        f"<b>⏱ Длительность:</b> {format_duration(duration_seconds)}\n"
        f"<b>💾 Размер:</b> {format_bytes(file_size_bytes)}\n"
        f'<b>🔗 Источник:</b> <a href="{escape(source_url)}">Открыть на YouTube</a>'
    )


def build_file_too_large_caption(
    *,
    title: str,
    quality: YoutubeDownloadOption,
    file_size_bytes: int,
    upload_limit_bytes: int,
) -> str:
    return (
        "<b>⚠️ Не удалось загрузить видео в Telegram</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"<b>📌 Название</b>\n{escape(title)}\n\n"
        f"<b>🎞 Выбранное качество:</b> {escape(quality.label)}\n"
        f"<b>💾 Итоговый размер:</b> {format_bytes(file_size_bytes)}\n"
        f"<b>📦 Лимит Telegram:</b> {format_bytes(upload_limit_bytes)}\n"
        "━━━━━━━━━━━━━━\n"
        "<i>Попробуйте выбрать вариант с меньшим качеством.</i>"
    )


def build_youtube_auth_required_caption() -> str:
    return (
        "<b>🔐 YouTube требует авторизацию</b>\n"
        "━━━━━━━━━━━━━━\n"
        "YouTube попросил подтвердить, что скачивание выполняет не бот.\n\n"
        "<b>Настройте один из вариантов:</b>\n"
        "• <code>YOUTUBE_COOKIES_PATH</code> — путь к cookies в формате Netscape\n"
        "• <code>YOUTUBE_COOKIES_FROM_BROWSER</code> — название браузера\n\n"
        "<i>Пример:</i> <code>YOUTUBE_COOKIES_FROM_BROWSER=chrome</code>"
    )


def build_youtube_browser_cookies_unsupported_caption() -> str:
    return (
        "<b>⚠️ Cookies браузера недоступны внутри контейнера</b>\n"
        "━━━━━━━━━━━━━━\n"
        "Бот работает в Linux-контейнере, а cookies браузера находятся на основной системе.\n\n"
        "<b>Используйте файл cookies:</b>\n"
        "• экспортируйте cookies YouTube в формате Netscape\n"
        "• смонтируйте файл в контейнер\n"
        "• укажите путь в <code>YOUTUBE_COOKIES_PATH</code>\n\n"
        "Не используйте <code>YOUTUBE_COOKIES_FROM_BROWSER</code> при запуске в контейнере."
    )
