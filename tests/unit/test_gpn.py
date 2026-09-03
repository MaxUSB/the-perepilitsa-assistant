import asyncio
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import httpx
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from src.core.gpn import GpnConfig, Station
from src.logic.gpn.client import GpnClient
from src.logic.gpn.module import GpnModule, dismiss_gpn_notification
from src.logic.gpn.store import GpnStateStore

_RECIPIENT_COUNT = 2


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


def create_module(*, recipient_ids: frozenset[int] = frozenset({1})) -> tuple[GpnModule, AsyncMock, AsyncMock]:
    bot = AsyncMock(spec=Bot)
    client = AsyncMock(spec=GpnClient)
    config = GpnConfig.model_validate(
        {
            "GPN_URL": "https://example.com",
            "GPN_INTERVAL_SECONDS": 60,
            "GPN_REQUEST_TIMEOUT_SECONDS": 30,
            "GPN_RECIPIENT_IDS": recipient_ids,
        }
    )
    module = GpnModule(bot=cast(Bot, bot), config=config)
    module._client = cast(GpnClient, client)
    store = MagicMock(spec=GpnStateStore)
    store.load.return_value = None
    module._store = cast(GpnStateStore, store)
    return module, bot, client


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

    client = GpnClient(
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


def test_finds_only_false_to_true_oil_transitions() -> None:
    previous = [station(oils={"92": False, "95": True, "G-100": False})]
    current = [station(oils={"92": True, "95": False, "G-100": False, "ДТ": True})]

    notifications = GpnModule._find_newly_available_fuels(previous, current)

    assert len(notifications) == 1
    assert notifications[0].oils == ("92",)


def test_groups_multiple_appeared_oils_by_station() -> None:
    previous = [station(oils={"92": False, "95": False})]
    current = [station(oils={"92": True, "95": True})]

    notifications = GpnModule._find_newly_available_fuels(previous, current)

    assert len(notifications) == 1
    assert notifications[0].oils == ("92", "95")


def test_ignores_new_station_and_new_oil_without_previous_false_value() -> None:
    previous = [station(station_id=1, oils={"92": True})]
    current = [
        station(station_id=1, oils={"92": True, "95": True}),
        station(station_id=2, oils={"92": True}),
    ]

    assert GpnModule._find_newly_available_fuels(previous, current) == []


async def test_first_response_only_initializes_state() -> None:
    module, bot, client = create_module()
    client.get_city_stations.return_value = [station(oils={"95": True})]

    await module._check_api()

    assert module._state == [station(oils={"95": True})]
    bot.send_message.assert_not_awaited()


async def test_first_response_is_compared_with_restored_state() -> None:
    module, bot, client = create_module()
    store = cast(MagicMock, module._store)
    store.load.return_value = [station(oils={"95": False})]
    client.get_city_stations.return_value = [station(oils={"95": True})]
    notification_sent = asyncio.Event()

    async def send_message(**kwargs: object) -> None:
        _ = kwargs
        notification_sent.set()

    bot.send_message.side_effect = send_message

    await module.startup()
    await asyncio.wait_for(notification_sent.wait(), timeout=1)
    await module.shutdown()

    bot.send_message.assert_awaited_once()
    store.save.assert_called_once_with([station(oils={"95": True})])


async def test_combines_all_changed_stations_into_one_message_per_recipient() -> None:
    module, bot, client = create_module(recipient_ids=frozenset({1, 2}))
    client.get_city_stations.side_effect = [
        [
            station(station_id=1, oils={"95": False}),
            station(station_id=2, oils={"92": False, "G-100": False}, address="Широтная, 6"),
        ],
        [
            station(station_id=1, oils={"95": True}),
            station(station_id=2, oils={"92": True, "G-100": True}, address="Широтная, 6"),
        ],
    ]

    await module._check_api()
    await module._check_api()

    assert bot.send_message.await_count == _RECIPIENT_COUNT
    call = bot.send_message.await_args_list[0]
    text = call.kwargs["text"]
    assert "⛽️" in text
    assert "Республики, 1" in text
    assert "Тюмень" not in text
    assert 'href="https://2gis.ru/tyumen?m=65.5%2C57.1%2F17&traffic"' in text
    assert "В наличии: 95" in text
    assert "Широтная, 6" in text
    assert "В наличии: 92, G-100" in text
    assert call.kwargs["reply_markup"].inline_keyboard[0][0].text == "👌 Ок"


async def test_does_not_notify_when_oils_do_not_appear() -> None:
    module, bot, client = create_module()
    client.get_city_stations.side_effect = [
        [station(oils={"92": True, "95": True})],
        [station(oils={"92": False, "95": True}, address="Новый адрес")],
    ]

    await module._check_api()
    await module._check_api()

    bot.send_message.assert_not_awaited()


async def test_fuel_command_deletes_command_and_shows_grouped_fuel_buttons() -> None:
    module, _, _ = create_module()
    module._state = [
        station(station_id=1, oils={"95": False, "G-95": True, "ДТ": True}),
        station(station_id=2, oils={"92": True}, address="Широтная, 6"),
    ]
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    message.delete = AsyncMock()

    await module._handle_fuel_command(cast(Message, message))

    message.delete.assert_awaited_once()
    message.answer.assert_awaited_once()
    call = message.answer.await_args
    assert call is not None
    assert "Какое топливо вас интересует?" in call.args[0]
    buttons = [button for row in call.kwargs["reply_markup"].inline_keyboard for button in row]
    assert [button.text for button in buttons] == ["⛽ 92", "⛽ 95", "⛽ ДТ"]
    assert [button.callback_data for button in buttons] == ["gpn:fuel:92", "gpn:fuel:95", "gpn:fuel:ДТ"]


async def test_fuel_command_reports_that_initial_state_is_loading() -> None:
    module, _, _ = create_module()
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    message.delete = AsyncMock()

    await module._handle_fuel_command(cast(Message, message))

    message.answer.assert_awaited_once()
    message.delete.assert_awaited_once()
    call = message.answer.await_args
    assert call is not None
    assert "Данные о топливе ещё загружаются" in call.args[0]
    assert call.kwargs["reply_markup"].inline_keyboard[0][0].text == "👌 Ок"


async def test_fuel_command_handles_empty_fuel_list() -> None:
    module, _, _ = create_module()
    module._state = []
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    message.delete = AsyncMock()

    await module._handle_fuel_command(cast(Message, message))

    message.answer.assert_awaited_once()
    call = message.answer.await_args
    assert call is not None
    assert "Данные о топливе не найдены" in call.args[0]
    assert call.kwargs["reply_markup"].inline_keyboard[0][0].text == "👌 Ок"


async def test_fuel_selection_edits_menu_with_matching_stations_and_2gis_links() -> None:
    module, _, _ = create_module()
    module._state = [
        station(station_id=1, oils={"95": True, "G-95": False}),
        station(
            station_id=2,
            oils={"95": False, "G-95": True},
            address="Широтная, 6",
            latitude=57.2,
            longitude=65.6,
        ),
        station(station_id=3, oils={"95": False, "G-95": False}, address="Ямская, 1"),
    ]
    callback_query = AsyncMock(spec=CallbackQuery)
    callback_query.answer = AsyncMock()
    callback_query.data = "gpn:fuel:95"
    message = AsyncMock(spec=Message)
    message.edit_text = AsyncMock()
    callback_query.message = message

    await module._handle_fuel_selection(cast(CallbackQuery, callback_query))

    callback_query.answer.assert_awaited_once()
    message.edit_text.assert_awaited_once()
    call = message.edit_text.await_args
    assert call is not None
    text = call.args[0]
    assert "Где есть топливо 95" in text
    assert "Республики, 1" in text
    assert "🔥 95" in text
    assert "Широтная, 6" in text
    assert "🔥 G-95" in text
    assert "Ямская, 1" not in text
    assert "Тюмень" not in text
    assert 'href="https://2gis.ru/tyumen?m=65.5%2C57.1%2F17&traffic"' in text
    assert 'href="https://2gis.ru/tyumen?m=65.6%2C57.2%2F17&traffic"' in text
    assert call.kwargs["reply_markup"].inline_keyboard[0][0].text == "👌 Ок"


async def test_fuel_selection_handles_stale_group() -> None:
    module, _, _ = create_module()
    module._state = [station(oils={"92": True})]
    callback_query = AsyncMock(spec=CallbackQuery)
    callback_query.answer = AsyncMock()
    callback_query.data = "gpn:fuel:95"
    message = AsyncMock(spec=Message)
    message.edit_text = AsyncMock()
    callback_query.message = message

    await module._handle_fuel_selection(cast(CallbackQuery, callback_query))

    callback_query.answer.assert_awaited_once()
    message.edit_text.assert_awaited_once()
    call = message.edit_text.await_args
    assert call is not None
    assert "Данные обновились" in call.args[0]


async def test_dismiss_callback_answers_and_deletes_message() -> None:
    callback_query = AsyncMock(spec=CallbackQuery)
    message = AsyncMock(spec=Message)
    callback_query.answer = AsyncMock()
    message.delete = AsyncMock()
    callback_query.message = message

    await dismiss_gpn_notification(cast(CallbackQuery, callback_query))

    callback_query.answer.assert_awaited_once()
    message.delete.assert_awaited_once()


async def test_dismiss_callback_ignores_already_deleted_message() -> None:
    callback_query = AsyncMock(spec=CallbackQuery)
    message = AsyncMock(spec=Message)
    callback_query.answer = AsyncMock()
    message.delete = AsyncMock()
    message.delete.side_effect = TelegramBadRequest(method=AsyncMock(), message="message not found")
    callback_query.message = message

    await dismiss_gpn_notification(cast(CallbackQuery, callback_query))

    callback_query.answer.assert_awaited_once()
    message.delete.assert_awaited_once()


async def test_module_starts_background_task_and_closes_client_on_shutdown() -> None:
    module, _, client = create_module()
    request_started = asyncio.Event()

    async def get_city_stations(city: str) -> list[Station]:
        assert city == "Тюмень"
        request_started.set()
        return []

    client.get_city_stations.side_effect = get_city_stations

    await module.startup()
    await asyncio.wait_for(request_started.wait(), timeout=1)

    assert module._task is not None
    assert not module._task.done()

    await module.shutdown()

    assert module._task is None
    client.close.assert_awaited_once()
