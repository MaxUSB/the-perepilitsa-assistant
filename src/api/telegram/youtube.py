import asyncio
from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.api.telegram.callbacks import YoutubeDownloadCallback
from src.api.telegram.filters import YoutubeUrlFilter
from src.core.youtube.models import YoutubeDownloadOption, YoutubeVideoPreview
from src.core.youtube.utils import (
    build_no_uploadable_formats_caption,
    build_preview_caption,
    build_youtube_auth_required_caption,
    build_youtube_browser_cookies_unsupported_caption,
    format_bytes,
)
from src.logic.youtube.client import YoutubeAuthenticationRequiredError, YoutubeBrowserCookiesUnsupportedError
from src.logic.youtube.service import YoutubeService


def create_youtube_router(background_tasks: set[asyncio.Task[None]]) -> Router:
    router = Router(name="youtube")

    @router.message(F.text, YoutubeUrlFilter())
    async def handle_youtube_message(message: Message, youtube_url: str, youtube_service: YoutubeService) -> None:
        try:
            preview_request = await youtube_service.create_request_from_message(
                message=message,
                youtube_url=youtube_url,
            )
        except YoutubeAuthenticationRequiredError:
            await message.answer(build_youtube_auth_required_caption())
            return
        except YoutubeBrowserCookiesUnsupportedError:
            await message.answer(build_youtube_browser_cookies_unsupported_caption())
            return

        uploadable_options = youtube_service.filter_uploadable_options(preview_request.preview.options)
        if not uploadable_options:
            await send_no_uploadable_formats_message(
                message=message,
                preview=preview_request.preview,
                upload_limit_bytes=youtube_service.telegram_upload_limit_bytes,
            )
            return

        reply_markup = build_quality_keyboard(
            request_id=preview_request.request_id,
            options=uploadable_options,
        )
        preview = preview_request.preview.model_copy(update={"options": uploadable_options})

        preview_message = await send_preview_message(
            message=message,
            preview=preview,
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
            await callback_query.answer("⌛ Срок действия запроса истёк", show_alert=True)
            with suppress(TelegramBadRequest):
                await message.delete()
            return

        progress_message = await message.answer(
            "<b>⏳ Подготовка к скачиванию</b>\n"
            "━━━━━━━━━━━━━━\n"
            "<code>[--------------------] 000.0%</code>\n\n"
            "<i>Подготавливаю всё необходимое...</i>"
        )
        await callback_query.answer("🚀 Скачивание началось")
        with suppress(TelegramBadRequest):
            await message.delete()

        download_task = asyncio.create_task(
            youtube_service.process_download(
                request_id=callback_data.request_id,
                option_key=callback_data.option_key,
                chat_id=message.chat.id,
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


async def send_no_uploadable_formats_message(
    *,
    message: Message,
    preview: YoutubeVideoPreview,
    upload_limit_bytes: int,
) -> Message:
    caption = build_no_uploadable_formats_caption(preview=preview, upload_limit_bytes=upload_limit_bytes)
    if preview.thumbnail_url is None:
        return await message.answer(caption)

    try:
        return await message.answer_photo(
            photo=str(preview.thumbnail_url),
            caption=caption,
        )
    except TelegramBadRequest:
        return await message.answer(caption)
