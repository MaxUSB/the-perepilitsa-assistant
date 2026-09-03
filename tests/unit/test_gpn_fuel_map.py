# ruff: noqa: SLF001

import asyncio
from typing import cast
from unittest.mock import AsyncMock

import httpx
from aiogram import Bot

from src.core.gpn_fuel_map.config import GpnFuelMapConfig
from src.logic.gpn_fuel_map.client import GpnFuelMapClient, Station
from src.logic.gpn_fuel_map.module import GpnFuelMapModule

_RECIPIENT_COUNT = 2


def create_module(*, recipient_ids: frozenset[int] = frozenset({1})) -> tuple[GpnFuelMapModule, AsyncMock, AsyncMock]:
    bot = AsyncMock(spec=Bot)
    client = AsyncMock(spec=GpnFuelMapClient)
    config = GpnFuelMapConfig.model_validate(
        {
            "GPN_FUEL_MAP_URL": "https://example.com",
            "GPN_FUEL_MAP_INTERVAL_SECONDS": 60,
            "GPN_FUEL_MAP_REQUEST_TIMEOUT_SECONDS": 30,
            "GPN_FUEL_MAP_RECIPIENT_IDS": recipient_ids,
        }
    )
    module = GpnFuelMapModule(bot=cast(Bot, bot), config=config)
    module._client = cast(GpnFuelMapClient, client)
    return module, bot, client


async def test_client_keeps_rotated_csrf_cookies_between_requests() -> None:
    requests: list[httpx.Request] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        response_number = len(requests)
        return httpx.Response(
            200,
            headers=[
                ("set-cookie", f"session-cookie=session-{response_number}; Path=/; Secure; HttpOnly"),
                ("set-cookie", f"csrf-token-name=name-{response_number}; Path=/; Secure"),
                ("set-cookie", f"csrf-token-value=value-{response_number}; Path=/; Secure"),
            ],
            json={"stations": []},
        )

    client = GpnFuelMapClient(
        url="https://example.com",
        request_timeout_seconds=30,
        transport=httpx.MockTransport(handle_request),
    )

    await client.get_city_stations()
    await client.get_city_stations()
    await client.close()

    assert requests[0].headers["user-agent"].startswith("Mozilla/5.0")
    assert "session-cookie=session-1" in requests[1].headers["cookie"]
    assert "csrf-token-name=name-1" in requests[1].headers["cookie"]
    assert "csrf-token-value=value-1" in requests[1].headers["cookie"]


async def test_first_response_only_initializes_state() -> None:
    module, bot, client = create_module()
    client.get_fuel_map.return_value = {"stations": []}

    await module._check_api()

    assert module._state == {"stations": []}
    bot.send_message.assert_not_awaited()


async def test_changed_response_sends_notification() -> None:
    module, bot, client = create_module(recipient_ids=frozenset({1, 2}))
    client.get_fuel_map.side_effect = [{"stations": []}, {"stations": [{"id": 1}]}]

    await module._check_api()
    await module._check_api()

    assert bot.send_message.await_count == _RECIPIENT_COUNT


async def test_equal_response_does_not_send_notification() -> None:
    module, bot, client = create_module()
    client.get_fuel_map.side_effect = [{"stations": []}, {"stations": []}]

    await module._check_api()
    await module._check_api()

    bot.send_message.assert_not_awaited()


async def test_send_error_does_not_prevent_other_recipients_from_receiving_message() -> None:
    module, bot, client = create_module(recipient_ids=frozenset({1, 2}))
    client.get_fuel_map.side_effect = [{"stations": []}, {"stations": [{"id": 1}]}]
    bot.send_message.side_effect = [RuntimeError("Telegram unavailable"), None]

    await module._check_api()
    await module._check_api()

    assert bot.send_message.await_count == _RECIPIENT_COUNT


async def test_module_starts_background_task_and_closes_client_on_shutdown() -> None:
    module, _, client = create_module()
    request_started = asyncio.Event()

    async def get_fuel_map() -> Station:
        request_started.set()
        return {"stations": []}

    client.get_fuel_map.side_effect = get_fuel_map

    await module.startup()
    await asyncio.wait_for(request_started.wait(), timeout=1)

    assert module._task is not None
    assert not module._task.done()

    await module.shutdown()

    assert module._task is None
    client.close.assert_awaited_once()
