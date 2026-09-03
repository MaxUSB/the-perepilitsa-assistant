from __future__ import annotations

import asyncio
import contextlib
import html
import logging

from aiogram import Bot, Router

from src.core.gpn_fuel_map.config import GpnFuelMapConfig
from src.logic.gpn_fuel_map.client import GpnFuelMapClient

logger = logging.getLogger(__name__)


class GpnFuelMapModule:
    def __init__(self, *, bot: Bot, config: GpnFuelMapConfig) -> None:
        self._router = Router(name="gpn_fuel_map")
        self._bot = bot
        self._config = config
        self._client = (
            GpnFuelMapClient(url=config.url, request_timeout_seconds=config.request_timeout_seconds)
            if config.url is not None
            else None
        )
        self._state: list | None = None
        self._task: asyncio.Task[None] | None = None

    def router(self) -> Router:
        return self._router

    async def startup(self) -> None:
        if self._client is None:
            logger.info("GPN fuel map is disabled because GPN_FUEL_MAP_URL is not configured")
            return

        self._task = asyncio.create_task(self._poll(), name="gpn-fuel-map")
        logger.info("GPN fuel map started")

    async def shutdown(self) -> None:
        if self._task is None:
            return

        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _poll(self) -> None:
        while True:
            try:
                await self._check_api()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("GPN fuel map request failed")

            await asyncio.sleep(self._config.interval_seconds)

    async def _check_api(self) -> None:
        if self._client is None:
            return

        new_state = await self._client.get_fuel_map()
        previous_state = self._state
        self._state = new_state

        if previous_state is None or not self._should_notify(previous_state, new_state):
            return

        message = self._build_message(previous_state, new_state)
        for recipient_id in self._config.recipient_ids:
            try:
                await self._bot.send_message(chat_id=recipient_id, text=message)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Failed to send GPN fuel map notification to chat %s", recipient_id)

    def _should_notify(self, previous_state: list, new_state: list) -> bool:
        """Replace this comparison with conditions specific to the API response."""
        return previous_state != new_state

    def _build_message(self, previous_state: list, new_state: list) -> str:
        """Replace this formatter with the fields that should be sent to Telegram."""
        _ = previous_state
        return f"API data changed:\n<pre>{html.escape(repr(new_state))}</pre>"
