from __future__ import annotations

from aiogram import Router

from src.api.telegram.youtube import create_youtube_router


class YoutubeModule:
    def __init__(self) -> None:
        self._router = create_youtube_router()

    def router(self) -> Router:
        return self._router

    async def startup(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None
