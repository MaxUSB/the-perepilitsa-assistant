from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile, Message

from src.core.bot.config import BotConfig
from src.core.youtube.client import YoutubeClient
from src.core.youtube.config import YoutubeConfig
from src.core.youtube.models import (
    YoutubeDownloadOption,
    YoutubeDownloadProgressSnapshot,
    YoutubeDownloadRequest,
)
from src.core.youtube.utils import build_progress_caption, build_result_caption
from src.logic.youtube.store import YoutubeRequestStore

LOGGER = logging.getLogger(__name__)


class YoutubeService:
    def __init__(
        self,
        *,
        bot_config: BotConfig,
        youtube_client: YoutubeClient,
        youtube_store: YoutubeRequestStore,
        youtube_config: YoutubeConfig,
    ) -> None:
        self._bot_config = bot_config
        self._youtube_client = youtube_client
        self._youtube_store = youtube_store
        self._youtube_config = youtube_config

    async def create_request_from_message(self, *, message: Message, youtube_url: str) -> YoutubeDownloadRequest:
        preview = await self._youtube_client.inspect(youtube_url)
        request = YoutubeDownloadRequest(
            request_id=self._youtube_store.create_request_id(),
            user_id=message.from_user.id if message.from_user is not None else 0,
            chat_id=message.chat.id,
            source_message_id=message.message_id,
            preview=preview,
        )
        await self._youtube_store.save(request)
        return request

    async def attach_preview_message(self, *, request_id: str, preview_message_id: int) -> None:
        request = await self._youtube_store.get(request_id)
        if request is None:
            return

        await self._youtube_store.save(request.model_copy(update={"preview_message_id": preview_message_id}))

    async def get_request(self, request_id: str) -> YoutubeDownloadRequest | None:
        return await self._youtube_store.get(request_id)

    async def process_download(
        self,
        *,
        request_id: str,
        option_key: str,
        progress_message_id: int,
        bot: Bot,
    ) -> None:
        request = await self._youtube_store.pop(request_id)
        if request is None:
            return

        option = _find_option(request=request, option_key=option_key)
        if option is None:
            await self._safe_edit_message(
                bot=bot,
                chat_id=request.chat_id,
                message_id=progress_message_id,
                text="<b>Download Failed</b>\nRequested quality is no longer available.",
            )
            return

        progress_lock = asyncio.Lock()
        last_progress_text = ""
        last_update_monotonic = 0.0

        async def progress_callback(snapshot: YoutubeDownloadProgressSnapshot) -> None:
            nonlocal last_progress_text, last_update_monotonic

            progress_text = build_progress_caption(snapshot)
            loop_time = asyncio.get_running_loop().time()
            if (
                progress_text == last_progress_text
                or loop_time - last_update_monotonic < self._youtube_config.progress_update_interval_seconds
            ):
                return

            async with progress_lock:
                last_progress_text = progress_text
                last_update_monotonic = loop_time
                await self._safe_edit_message(
                    bot=bot,
                    chat_id=request.chat_id,
                    message_id=progress_message_id,
                    text=progress_text,
                )

        try:
            result = await self._youtube_client.download(
                url=request.preview.source_url,
                option=option,
                request_id=request_id,
                progress_callback=progress_callback,
            )
            await self._send_result_message(bot=bot, request=request, option=option, result_file=result.file_path)
            await self._safe_delete_message(bot=bot, chat_id=request.chat_id, message_id=progress_message_id)
            if self._bot_config.delete_source_message:
                await self._safe_delete_message(
                    bot=bot,
                    chat_id=request.chat_id,
                    message_id=request.source_message_id,
                )
        except Exception:
            LOGGER.exception("YouTube download failed for request %s", request_id)
            await self._safe_edit_message(
                bot=bot,
                chat_id=request.chat_id,
                message_id=progress_message_id,
                text="<b>Download Failed</b>\nThe video could not be downloaded right now.",
            )
        finally:
            if hasattr(self._youtube_client, "cleanup_request_files"):
                await self._youtube_client.cleanup_request_files(request_id)

    async def _send_result_message(
        self,
        *,
        bot: Bot,
        request: YoutubeDownloadRequest,
        option: YoutubeDownloadOption,
        result_file: Path,
    ) -> None:
        file_size_bytes = await asyncio.to_thread(lambda: result_file.stat().st_size)
        result_caption = build_result_caption(
            title=request.preview.title,
            quality_label=option.label,
            duration_seconds=request.preview.duration_seconds,
            file_size_bytes=file_size_bytes,
            source_url=request.preview.source_url,
        )
        await bot.send_video(
            chat_id=request.chat_id,
            video=FSInputFile(result_file),
            caption=result_caption,
            supports_streaming=True,
        )

    async def _safe_edit_message(self, *, bot: Bot, chat_id: int, message_id: int, text: str) -> None:
        with contextlib.suppress(Exception):
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text)

    async def _safe_delete_message(self, *, bot: Bot, chat_id: int, message_id: int) -> None:
        with contextlib.suppress(Exception):
            await bot.delete_message(chat_id=chat_id, message_id=message_id)


def _find_option(*, request: YoutubeDownloadRequest, option_key: str) -> YoutubeDownloadOption | None:
    for option in request.preview.options:
        if option.key == option_key:
            return option
    return None
