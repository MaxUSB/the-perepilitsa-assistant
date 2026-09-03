import asyncio
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import httpx
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from src.api.telegram.callbacks import GpnFuelCallback
from src.api.telegram.gpn import (
    DISMISS_KEYBOARD,
    build_availability_message,
    build_fuel_keyboard,
    build_fuel_stations_message,
    dismiss_gpn_notification,
    handle_fuel_command,
    handle_fuel_selection,
)
from src.core.gpn import FuelAvailability, GpnConfig, Station
from src.logic.gpn.client import HttpGpnClient
from src.logic.gpn.module import GpnModule
from src.logic.gpn.service import GpnService
from src.logic.gpn.store import GpnStateStore

_RECIPIENT_COUNT = 2
_STATION_COUNT = 2


def station(
    *,
    station_id: int = 1,
    oils: dict[str, bool],
    address: str = "Республики, 1",
    latitude: float = 57.1,
    longitude: float = 65.5,
) -> Station:
    return Station(
        id=station_id,
        city="Тюмень",
        address=address,
        latitude=latitude,
        longitude=longitude,
        oils=oils,
    )


def create_service(*, city: str = "Тюмень") -> tuple[GpnService, AsyncMock, MagicMock]:
    client = AsyncMock(spec=HttpGpnClient)
    store = MagicMock(spec=GpnStateStore)
    store.load.return_value = None
    service = GpnService(city=city, client=client, store=store)
    return service, client, store


def create_module(*, recipient_ids: frozenset[int] = frozenset({1})) -> tuple[GpnModule, GpnService, AsyncMock]:
    bot = AsyncMock(spec=Bot)
    service, _, _ = create_service()
    config = GpnConfig.model_validate(
        {
            "url": "https://example.com",
            "city": "Тюмень",
            "interval_seconds": 60,
            "request_timeout_seconds": 30,
            "recipient_ids": recipient_ids,
            "state_path": ".runtime/gpn/state.json",
        }
    )
    return GpnModule(bot=cast(Bot, bot), config=config, service=service), service, bot


async def test_client_keeps_rotated_csrf_cookies_and_parses_station_oils() -> None:
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
            json={
                "oilProducts": [{"id": 12, "shortTitle": "95"}],
                "stations": [
                    {
                        "GPNAZSID": 1,
                        "city": "Тюмень",
                        "address": "Республики, 1",
                        "latitude": "57.1",
                        "longitude": "65.5",
                        "oils": {"12": True},
                    },
                    {
                        "GPNAZSID": 2,
                        "city": "Москва",
                        "address": "Тверская, 1",
                        "latitude": "55.7",
                        "longitude": "37.6",
                        "oils": {"12": True},
                    },
                ],
            },
        )

    client = HttpGpnClient(
        url="https://example.com",
        request_timeout_seconds=30,
        transport=httpx.MockTransport(handle_request),
    )
    stations = await client.get_city_stations("Тюмень")
    await client.get_city_stations("Тюмень")
    await client.close()

    assert stations == [station(oils={"95": True})]
    assert requests[0].headers["user-agent"].startswith("Mozilla/5.0")
    assert "session-cookie=session-1" in requests[1].headers["cookie"]
    assert "csrf-token-name=name-1" in requests[1].headers["cookie"]
    assert "csrf-token-value=value-1" in requests[1].headers["cookie"]


def test_state_store_persists_and_restores_stations(tmp_path: Path) -> None:
    state_store = GpnStateStore(tmp_path / "gpn" / "state.json")
    stations = [station(oils={"95": True, "G-95": False})]
    state_store.save(stations)
    assert state_store.load() == stations


def test_state_store_returns_none_for_corrupted_state(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text("not-json")
    assert GpnStateStore(state_path).load() is None


async def test_service_refresh_finds_only_false_to_true_transitions_and_persists_state() -> None:
    service, client, store = create_service()
    store.load.return_value = [station(oils={"92": False, "95": True, "ДТ": False})]
    client.get_city_stations.return_value = [station(oils={"92": True, "95": False, "ДТ": True, "G-100": True})]
    await service.restore()

    notifications = await service.refresh()

    assert notifications[0].oils == ("92", "ДТ")
    store.save.assert_called_once_with(client.get_city_stations.return_value)


async def test_service_first_refresh_only_initializes_state() -> None:
    service, client, _ = create_service(city="Екатеринбург")
    client.get_city_stations.return_value = [station(oils={"95": True})]
    assert await service.refresh() == []
    client.get_city_stations.assert_awaited_once_with("Екатеринбург")
    assert service.get_fuel_groups() == {"95": ("95",)}


async def test_service_ignores_restored_state_from_another_city() -> None:
    service, _, store = create_service(city="Екатеринбург")
    store.load.return_value = [station(oils={"95": True})]

    assert await service.restore() is None
    assert service.get_fuel_groups() is None


def test_service_groups_octane_variants_and_filters_available_stations() -> None:
    service, _, store = create_service()
    store.load.return_value = [
        station(station_id=1, oils={"95": True, "G-95": False, "ДТ": True}),
        station(station_id=2, oils={"95": False, "G-95": True}, address="Широтная, 6"),
    ]
    service._state = store.load.return_value

    assert service.get_fuel_groups() == {"95": ("95", "G-95"), "ДТ": ("ДТ",)}
    oil_names, stations = service.get_stations_for_group("95") or ((), [])
    assert oil_names == ("95", "G-95")
    assert len(stations) == _STATION_COUNT
    assert service.get_stations_for_group("100") is None


async def test_module_sends_combined_notification_to_each_recipient() -> None:
    module, service, bot = create_module(recipient_ids=frozenset({1, 2}))
    service.refresh = AsyncMock(
        return_value=[
            FuelAvailability(station=station(oils={"95": True}), oils=("95",)),
            FuelAvailability(station=station(station_id=2, oils={"92": True}, address="Широтная, 6"), oils=("92",)),
        ]
    )

    await module._check_api()

    assert bot.send_message.await_count == _RECIPIENT_COUNT
    assert "Республики, 1" in bot.send_message.await_args_list[0].kwargs["text"]
    assert "Широтная, 6" in bot.send_message.await_args_list[0].kwargs["text"]


async def test_module_restores_state_starts_polling_and_closes_service() -> None:
    module, service, _ = create_module()
    request_started = asyncio.Event()
    service.restore = AsyncMock(return_value=[station(oils={"95": False})])

    async def refresh() -> list[FuelAvailability]:
        request_started.set()
        return []

    service.refresh = AsyncMock(side_effect=refresh)
    service.close = AsyncMock()
    await module.startup()
    await asyncio.wait_for(request_started.wait(), timeout=1)
    await module.shutdown()

    service.restore.assert_awaited_once()
    service.close.assert_awaited_once()
    assert module._task is None


async def test_fuel_command_deletes_command_and_shows_grouped_buttons() -> None:
    service = MagicMock(spec=GpnService)
    service.get_fuel_groups.return_value = {"92": ("92",), "95": ("95", "G-95"), "ДТ": ("ДТ",)}
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    message.delete = AsyncMock()

    await handle_fuel_command(cast(Message, message), service)

    message.delete.assert_awaited_once()
    call = message.answer.await_args
    assert call is not None
    buttons = [button for row in call.kwargs["reply_markup"].inline_keyboard for button in row]
    assert [button.text for button in buttons] == ["⛽ 92", "⛽ 95", "⛽ ДТ"]
    assert [button.callback_data for button in buttons] == ["gpn_fuel:92", "gpn_fuel:95", "gpn_fuel:ДТ"]


async def test_fuel_command_reports_loading_state() -> None:
    service = MagicMock(spec=GpnService)
    service.get_fuel_groups.return_value = None
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    message.delete = AsyncMock()

    await handle_fuel_command(cast(Message, message), service)

    call = message.answer.await_args
    assert call is not None
    assert "Данные о топливе ещё загружаются" in call.args[0]
    assert call.kwargs["reply_markup"] == DISMISS_KEYBOARD


async def test_fuel_selection_edits_message_with_matching_stations() -> None:
    service = MagicMock(spec=GpnService)
    stations = [
        station(oils={"95": True, "G-95": False}),
        station(station_id=2, oils={"95": False, "G-95": True}, address="Широтная, 6"),
    ]
    service.get_stations_for_group.return_value = (("95", "G-95"), stations)
    callback_query = AsyncMock(spec=CallbackQuery)
    callback_query.answer = AsyncMock()
    message = AsyncMock(spec=Message)
    message.edit_text = AsyncMock()
    callback_query.message = message

    await handle_fuel_selection(
        cast(CallbackQuery, callback_query),
        GpnFuelCallback(group_key="95"),
        service,
    )

    callback_query.answer.assert_awaited_once()
    call = message.edit_text.await_args
    assert call is not None
    assert "Где есть топливо 95" in call.args[0]
    assert "Республики, 1" in call.args[0]
    assert "Широтная, 6" in call.args[0]
    assert "Тюмень" not in call.args[0]


async def test_dismiss_callback_answers_and_deletes_message() -> None:
    callback_query = AsyncMock(spec=CallbackQuery)
    callback_query.answer = AsyncMock()
    message = AsyncMock(spec=Message)
    message.delete = AsyncMock()
    callback_query.message = message

    await dismiss_gpn_notification(cast(CallbackQuery, callback_query))

    callback_query.answer.assert_awaited_once()
    message.delete.assert_awaited_once()


def test_gpn_message_builders_include_2gis_links_and_escape_values() -> None:
    current_station = station(oils={"95": True}, address="Республики <1>")
    availability = build_availability_message([FuelAvailability(station=current_station, oils=("95",))])
    station_list = build_fuel_stations_message("95", ("95",), [current_station])

    assert "Республики &lt;1&gt;" in availability
    assert "https://2gis.ru/?m=65.5%2C57.1%2F17&traffic" in availability
    assert "Республики &lt;1&gt;" in station_list
    assert build_fuel_keyboard({"95": ("95",)}).inline_keyboard[0][0].text == "⛽ 95"


async def test_dismiss_callback_ignores_already_deleted_message() -> None:
    callback_query = AsyncMock(spec=CallbackQuery)
    callback_query.answer = AsyncMock()
    message = AsyncMock(spec=Message)
    message.delete = AsyncMock(side_effect=TelegramBadRequest(method=AsyncMock(), message="message not found"))
    callback_query.message = message

    await dismiss_gpn_notification(cast(CallbackQuery, callback_query))

    callback_query.answer.assert_awaited_once()
    message.delete.assert_awaited_once()
