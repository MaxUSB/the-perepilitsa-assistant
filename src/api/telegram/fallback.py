from aiogram import Router
from aiogram.types import Message

FALLBACK_MESSAGE = "<b>⚠️ Не удалось распознать сообщение</b>"


def create_fallback_router() -> Router:
    router = Router(name="fallback")

    @router.message()
    async def handle_fallback(message: Message) -> None:
        await message.answer(FALLBACK_MESSAGE)

    return router
