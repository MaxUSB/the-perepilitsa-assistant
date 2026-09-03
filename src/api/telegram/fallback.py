from aiogram import Router
from aiogram.types import Message

FALLBACK_MESSAGE = (
    "<b>⚠️ Не удалось распознать сообщение</b>\n"
    "━━━━━━━━━━━━━━\n"
    "Попробуйте отправить что-нибудь из примеров ниже:\n\n"
    "• 🎬 <b>Ссылка на YouTube</b>\n"
    "  <i>youtube.com</i>\n\n"
    "• ⛽️ <b>Поиск топлива на АЗС</b>\n"
    "  <i>/fuel</i>"
)


def create_fallback_router() -> Router:
    router = Router(name="fallback")

    @router.message()
    async def handle_fallback(message: Message) -> None:
        await message.answer(FALLBACK_MESSAGE)

    return router
