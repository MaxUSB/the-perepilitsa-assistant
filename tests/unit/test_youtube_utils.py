from src.core.youtube.models import (
    YoutubeDownloadOption,
    YoutubeDownloadProgressSnapshot,
    YoutubeVideoPreview,
)
from src.core.youtube.utils import (
    build_file_too_large_caption,
    build_preview_caption,
    build_progress_caption,
    build_result_caption,
    build_youtube_auth_required_caption,
    build_youtube_browser_cookies_unsupported_caption,
    extract_youtube_url,
    format_bytes,
    format_duration,
    render_progress_bar,
)


def test_extract_youtube_url_accepts_watch_links() -> None:
    text = "check this https://www.youtube.com/watch?v=dQw4w9WgXcQ right now"
    assert extract_youtube_url(text) == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_extract_youtube_url_rejects_non_youtube_links() -> None:
    assert extract_youtube_url("https://example.com/video") is None


def test_format_helpers_return_expected_values() -> None:
    assert format_bytes(1024) == "1.0 KiB"
    assert format_duration(65) == "01:05"
    assert render_progress_bar(0.5, width=10) == "[#####-----]"


def test_build_preview_caption_contains_metadata() -> None:
    preview = YoutubeVideoPreview(
        source_url="https://youtu.be/example",
        title="Video title",
        uploader="Author",
        duration_seconds=120,
        options=(
            YoutubeDownloadOption(
                key="720p",
                label="720p mp4",
                selector="best",
                container="mp4",
                height=720,
                estimated_size_bytes=123456,
            ),
        ),
    )

    caption = build_preview_caption(preview)

    assert "Video title" in caption
    assert "Author" in caption
    assert "Доступно вариантов:" in caption
    assert "Выберите качество для скачивания" in caption


def test_build_progress_caption_contains_progress_values() -> None:
    caption = build_progress_caption(
        YoutubeDownloadProgressSnapshot(
            status="downloading",
            downloaded_bytes=50,
            total_bytes=100,
            speed_bytes_per_second=20,
            eta_seconds=10,
        )
    )

    assert "50.0%" in caption
    assert "20 B/с" in caption


def test_build_progress_caption_clamps_percentage_to_one_hundred() -> None:
    caption = build_progress_caption(
        YoutubeDownloadProgressSnapshot(
            status="downloading",
            downloaded_bytes=150,
            total_bytes=100,
        )
    )

    assert "100.0%" in caption
    assert "150.0%" not in caption


def test_youtube_user_messages_are_russian() -> None:
    option = YoutubeDownloadOption(
        key="720p",
        label="720p mp4",
        selector="best",
        container="mp4",
    )

    result_caption = build_result_caption(
        title="Название",
        quality_label=option.label,
        duration_seconds=60,
        file_size_bytes=1024,
        source_url="https://youtu.be/example",
    )
    too_large_caption = build_file_too_large_caption(
        title="Название",
        quality=option,
        file_size_bytes=2048,
        upload_limit_bytes=1024,
    )

    assert "Видео готово" in result_caption
    assert "Открыть на YouTube" in result_caption
    assert "Не удалось загрузить видео" in too_large_caption
    assert "YouTube требует авторизацию" in build_youtube_auth_required_caption()
    assert "Cookies браузера недоступны" in build_youtube_browser_cookies_unsupported_caption()
