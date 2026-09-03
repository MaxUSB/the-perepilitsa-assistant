import asyncio
import contextlib
import logging

from aiogram import Bot, Router

from src.api.telegram.gpn import DISMISS_KEYBOARD, build_availability_message, create_gpn_router
from src.core.gpn import GpnConfig
from src.logic.gpn.service import GpnService

logger = logging.getLogger(__name__)


class GpnModule:
    def __init__(self, *, bot: Bot, config: GpnConfig, service: GpnService) -> None:
        self._router = create_gpn_router()
        self._bot = bot
        self._config = config
        self._service = service
        self._task: asyncio.Task[None] | None = None

    def router(self) -> Router:
        return self._router

    async def startup(self) -> None:
        state = await self._service.restore()
        if state is not None:
            logger.info("Restored GPN state with %s stations", len(state))

        if not self._service.enabled:
            logger.info("GPN module is disabled because GPN_URL is not configured")
            return

        self._task = asyncio.create_task(self._poll(), name="gpn")
        logger.info("GPN module started")

    async def shutdown(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        await self._service.close()

    async def _poll(self) -> None:
        while True:
            try:
                await self._check_api()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("GPN request failed")

            await asyncio.sleep(self._config.interval_seconds)

    async def _check_api(self) -> None:
        notifications = await self._service.refresh()
        if not notifications:
            return

        message = build_availability_message(notifications)
        for recipient_id in self._config.recipient_ids:
            try:
                await self._bot.send_message(
                    chat_id=recipient_id,
                    text=message,
                    reply_markup=DISMISS_KEYBOARD,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Failed to send GPN notification to chat %s", recipient_id)
