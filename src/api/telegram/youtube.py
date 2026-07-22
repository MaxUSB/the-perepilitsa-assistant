from __future__ import annotations

import asyncio
from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.api.telegram.callbacks import YoutubeDownloadCallback
from src.api.telegram.filters import YoutubeUrlFilter
from src.core.youtube.models import YoutubeDownloadOption, YoutubeVideoPreview
from src.core.youtube.utils import build_preview_caption, format_bytes
from src.logic.youtube.service import YoutubeService


def create_youtube_router() -> Router:
    router = Router(name="youtube")
    background_tasks: set[asyncio.Task[None]] = set()

    @router.message(F.text, YoutubeUrlFilter())
    async def handle_youtube_message(message: Message, youtube_url: str, youtube_service: YoutubeService) -> None:
        preview_request = await youtube_service.create_request_from_message(
            message=message,
            youtube_url=youtube_url,
        )
        reply_markup = build_quality_keyboard(
            request_id=preview_request.request_id,
            options=preview_request.preview.options,
        )

        preview_message = await send_preview_message(
            message=message,
            preview=preview_request.preview,
            reply_markup=reply_markup,
        )
        await youtube_service.attach_preview_message(
            request_id=preview_request.request_id,
            preview_message_id=preview_message.message_id,
        )

    @router.callback_query(YoutubeDownloadCallback.filter())
    async def handle_quality_selection(
        callback_query: CallbackQuery,
        callback_data: YoutubeDownloadCallback,
        youtube_service: YoutubeService,
    ) -> None:
        if callback_query.message is None or not isinstance(callback_query.message, Message):
            await callback_query.answer()
            return

        if callback_query.bot is None:
            await callback_query.answer()
            return

        message = callback_query.message
        bot = callback_query.bot

        download_request = await youtube_service.get_request(callback_data.request_id)
        if download_request is None:
            await callback_query.answer("⌛ This request has expired", show_alert=True)
            with suppress(TelegramBadRequest):
                await message.delete()
            return

        progress_message = await message.answer(
            "<b>⏳ Preparing Download</b>\n"
            "━━━━━━━━━━━━━━\n"
            "<code>[--------------------] 000.0%</code>\n\n"
            "<i>Getting everything ready...</i>"
        )
        await callback_query.answer("🚀 Download started")
        with suppress(TelegramBadRequest):
            await message.delete()

        download_task = asyncio.create_task(
            youtube_service.process_download(
                request_id=callback_data.request_id,
                option_key=callback_data.option_key,
                progress_message_id=progress_message.message_id,
                bot=bot,
            )
        )
        background_tasks.add(download_task)
        download_task.add_done_callback(background_tasks.discard)

    return router


def build_quality_keyboard(*, request_id: str, options: tuple[YoutubeDownloadOption, ...]) -> InlineKeyboardMarkup:
    keyboard_builder = InlineKeyboardBuilder()

    for option in options:
        keyboard_builder.button(
            text=f"🎞 {option.label} | 💾 {format_bytes(option.estimated_size_bytes)}",
            callback_data=YoutubeDownloadCallback(request_id=request_id, option_key=option.key).pack(),
        )

    keyboard_builder.adjust(1)
    return keyboard_builder.as_markup()


async def send_preview_message(
    *,
    message: Message,
    preview: YoutubeVideoPreview,
    reply_markup: InlineKeyboardMarkup,
) -> Message:
    caption = build_preview_caption(preview)
    if preview.thumbnail_url is None:
        return await message.answer(caption, reply_markup=reply_markup)

    try:
        return await message.answer_photo(
            photo=str(preview.thumbnail_url),
            caption=caption,
            reply_markup=reply_markup,
        )
    except TelegramBadRequest:
        return await message.answer(caption, reply_markup=reply_markup)
