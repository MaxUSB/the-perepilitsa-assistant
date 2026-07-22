from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message


def create_common_router() -> Router:
    router = Router(name="common")

    @router.message(CommandStart())
    async def handle_start(message: Message) -> None:
        await message.answer(
            "<b>🤖 The Perepilitsa Assistant</b>\n"
            "━━━━━━━━━━━━━━\n"
            "<b>What I can do right now:</b>\n"
            "• 🎬 detect a YouTube link automatically\n"
            "• 📋 show available qualities and file sizes\n"
            "• ⬇️ download the selected version in background\n"
            "• 📤 send the final video with useful details\n\n"
            "<i>Just send a YouTube link in one message.</i>"
        )

    return router
