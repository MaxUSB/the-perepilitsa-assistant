from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User


class AllowedUserMiddleware(BaseMiddleware):
    def __init__(self, allowed_user_ids: frozenset[int]) -> None:
        self._allowed_user_ids = allowed_user_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[object | None]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> object | None:
        event_from_user = data.get("event_from_user")
        if isinstance(event_from_user, User):
            user_id = event_from_user.id
            if user_id not in self._allowed_user_ids:
                return None

        return await handler(event, data)
