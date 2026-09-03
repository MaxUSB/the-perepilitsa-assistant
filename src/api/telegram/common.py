from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

WELCOME_MESSAGE = (
    "<b>🤖 The Perepilitsa Assistant</b>\n"
    "━━━━━━━━━━━━━━\n"
    "<b>Что можно отправить:</b>\n"
    "• 🎬 <b>Ссылка на YouTube</b>\n"
    "  <i>youtube.com</i>\n\n"
    "• ⛽️ <b>Поиск топлива на АЗС</b>\n"
    "  <i>/fuel</i>"
)


def create_common_router() -> Router:
    router = Router(name="common")

    @router.message(CommandStart())
    async def handle_start(message: Message) -> None:
        await message.answer(WELCOME_MESSAGE)

    return router
