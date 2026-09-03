import asyncio

from aiogram import Router

from src.api.telegram.youtube import create_youtube_router


class YoutubeModule:
    def __init__(self) -> None:
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._router = create_youtube_router(self._background_tasks)

    def router(self) -> Router:
        return self._router

    async def startup(self) -> None:
        return None

    async def shutdown(self) -> None:
        for task in self._background_tasks:
            task.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()
