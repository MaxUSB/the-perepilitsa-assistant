from __future__ import annotations

from typing import Protocol

from aiogram import Router


class BotModule(Protocol):
    def router(self) -> Router: ...

    async def startup(self) -> None: ...

    async def shutdown(self) -> None: ...
