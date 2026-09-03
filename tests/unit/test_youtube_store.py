from datetime import UTC, datetime, timedelta

from src.core.youtube.models import YoutubeDownloadOption, YoutubeDownloadRequest, YoutubeVideoPreview
from src.logic.youtube.store import YoutubeRequestStore


def test_store_removes_expired_requests() -> None:
    store = YoutubeRequestStore(request_ttl_seconds=60)
    request = YoutubeDownloadRequest(
        request_id="expired",
        user_id=1,
        chat_id=1,
        source_message_id=1,
        created_at=datetime.now(tz=UTC) - timedelta(seconds=120),
        preview=YoutubeVideoPreview(
            source_url="https://youtu.be/example",
            title="Example",
            options=(),
        ),
    )

    store.save(request)

    assert store.get("expired") is None


def test_store_claims_only_existing_valid_option() -> None:
    store = YoutubeRequestStore(request_ttl_seconds=60)
    option = YoutubeDownloadOption(key="720p", label="720p", selector="22", container="mp4")
    request = YoutubeDownloadRequest(
        request_id="request",
        user_id=1,
        chat_id=1,
        source_message_id=1,
        preview=YoutubeVideoPreview(
            source_url="https://youtu.be/example",
            title="Example",
            options=(option,),
        ),
    )
    store.save(request)

    assert store.claim("request", "invalid") is None
    assert store.get("request") == request
    assert store.claim("request", "720p") == request
    assert store.get("request") is None
