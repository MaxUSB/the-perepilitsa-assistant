# ruff: noqa: SLF001

import asyncio
from typing import cast
from unittest.mock import AsyncMock

from aiogram import Bot

from src.core.gpn_fuel_map.config import GpnFuelMapConfig
from src.logic.gpn_fuel_map.client import GpnFuelMapClient, JsonValue
from src.logic.gpn_fuel_map.module import GpnFuelMapModule

_RECIPIENT_COUNT = 2


def create_module(*, recipient_ids: frozenset[int] = frozenset({1})) -> tuple[GpnFuelMapModule, AsyncMock, AsyncMock]:
    bot = AsyncMock(spec=Bot)
    client = AsyncMock(spec=GpnFuelMapClient)
    config = GpnFuelMapConfig(url="https://example.com/status", interval_seconds=60, request_timeout_seconds=30)
    module = GpnFuelMapModule(bot=cast(Bot, bot), config=config, recipient_ids=recipient_ids)
    module._client = cast(GpnFuelMapClient, client)
    return module, bot, client


async def test_first_response_only_initializes_state() -> None:
    module, bot, client = create_module()
    client.fetch.return_value = {"value": 1}

    await module._check_api()

    assert module._state == {"value": 1}
    bot.send_message.assert_not_awaited()


async def test_changed_response_sends_notification() -> None:
    module, bot, client = create_module(recipient_ids=frozenset({1, 2}))
    client.fetch.side_effect = [{"value": 1}, {"value": 2}]

    await module._check_api()
    await module._check_api()

    assert bot.send_message.await_count == _RECIPIENT_COUNT


async def test_equal_response_does_not_send_notification() -> None:
    module, bot, client = create_module()
    client.fetch.side_effect = [{"value": 1}, {"value": 1}]

    await module._check_api()
    await module._check_api()

    bot.send_message.assert_not_awaited()


async def test_send_error_does_not_prevent_other_recipients_from_receiving_message() -> None:
    module, bot, client = create_module(recipient_ids=frozenset({1, 2}))
    client.fetch.side_effect = [{"value": 1}, {"value": 2}]
    bot.send_message.side_effect = [RuntimeError("Telegram unavailable"), None]

    await module._check_api()
    await module._check_api()

    assert bot.send_message.await_count == _RECIPIENT_COUNT


async def test_module_starts_background_task_and_cancels_it_on_shutdown() -> None:
    module, _, client = create_module()
    request_started = asyncio.Event()

    async def fetch() -> JsonValue:
        request_started.set()
        return {"value": 1}

    client.fetch.side_effect = fetch

    await module.startup()
    await asyncio.wait_for(request_started.wait(), timeout=1)

    assert module._task is not None
    assert not module._task.done()

    await module.shutdown()

    assert module._task is None
