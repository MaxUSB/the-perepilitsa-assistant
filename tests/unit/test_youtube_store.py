from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.core.youtube.models import YoutubeDownloadRequest, YoutubeVideoPreview
from src.logic.youtube.store import YoutubeRequestStore


@pytest.mark.asyncio
async def test_store_removes_expired_requests() -> None:
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

    await store.save(request)

    assert await store.get("expired") is None
