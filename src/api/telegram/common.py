from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

WELCOME_MESSAGE = (
    "<b>🤖 The Perepilitsa Assistant</b>\n"
    "━━━━━━━━━━━━━━\n"
    "<b>Модули:</b>\n\n"
    "🎬 <b>YouTube</b>\n"
    "  <i>youtube.com/some-path - скачивание видео</i>\n\n"
    "⛽️ <b>GPN</b>\n"
    "  <i>/notify_fuel - уведомления о наличии топлива</i>\n\n"
    "  <i>/fuel - наличие топлива</i>"
)


def create_common_router() -> Router:
    router = Router(name="common")

    @router.message(CommandStart())
    async def handle_start(message: Message) -> None:
        await message.answer(WELCOME_MESSAGE)

    return router
