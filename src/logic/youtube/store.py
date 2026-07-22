from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from src.core.youtube.models import YoutubeDownloadRequest


class YoutubeRequestStore:
    def __init__(self, *, request_ttl_seconds: int) -> None:
        self._request_ttl = timedelta(seconds=request_ttl_seconds)
        self._requests: dict[str, YoutubeDownloadRequest] = {}

    def create_request_id(self) -> str:
        return uuid4().hex[:12]

    async def save(self, request: YoutubeDownloadRequest) -> None:
        self._cleanup_expired()
        self._requests[request.request_id] = request

    async def get(self, request_id: str) -> YoutubeDownloadRequest | None:
        self._cleanup_expired()
        return self._requests.get(request_id)

    async def pop(self, request_id: str) -> YoutubeDownloadRequest | None:
        self._cleanup_expired()
        return self._requests.pop(request_id, None)

    def _cleanup_expired(self) -> None:
        now = datetime.now(tz=UTC)
        expired_ids = [
            request_id for request_id, request in self._requests.items() if now - request.created_at > self._request_ttl
        ]
        for request_id in expired_ids:
            self._requests.pop(request_id, None)
