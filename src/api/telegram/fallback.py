from __future__ import annotations

from aiogram import Router
from aiogram.types import Message


def create_fallback_router() -> Router:
    router = Router(name="fallback")

    @router.message()
    async def handle_fallback(message: Message) -> None:
        await message.answer(
            "<b>⚠️ Unsupported Input</b>\n"
            "━━━━━━━━━━━━━━\n"
            "Send a <b>YouTube link</b> to start the interactive download flow.\n\n"
            "<i>Example: https://youtu.be/...</i>"
        )

    return router
