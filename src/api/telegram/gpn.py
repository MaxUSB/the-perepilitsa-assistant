import contextlib
import html
from urllib.parse import quote

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.api.telegram.callbacks import GpnFuelCallback
from src.core.gpn import FuelAvailability, Station
from src.logic.gpn.service import GpnService

DISMISS_CALLBACK_DATA = "gpn:dismiss"
DISMISS_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="👌 Ок", callback_data=DISMISS_CALLBACK_DATA)]]
)


def create_gpn_router() -> Router:
    router = Router(name="gpn")
    router.message.register(handle_fuel_command, Command("fuel"))
    router.callback_query.register(handle_fuel_selection, GpnFuelCallback.filter())
    router.callback_query.register(dismiss_gpn_notification, F.data == DISMISS_CALLBACK_DATA)
    return router


async def handle_fuel_command(message: Message, gpn_service: GpnService) -> None:
    with contextlib.suppress(TelegramBadRequest):
        await message.delete()

    fuel_groups = gpn_service.get_fuel_groups()
    if fuel_groups is None:
        await message.answer(
            "⏳ <b>Данные о топливе ещё загружаются</b>\n\nПопробуйте выполнить команду /fuel чуть позже.",
            reply_markup=DISMISS_KEYBOARD,
        )
        return

    if not fuel_groups:
        await message.answer("⛽️ <b>Данные о топливе не найдены</b>", reply_markup=DISMISS_KEYBOARD)
        return

    await message.answer(
        "⛽️ <b>Какое топливо вас интересует?</b>",
        reply_markup=build_fuel_keyboard(fuel_groups),
    )


async def handle_fuel_selection(
    callback_query: CallbackQuery,
    callback_data: GpnFuelCallback,
    gpn_service: GpnService,
) -> None:
    await callback_query.answer()
    if not isinstance(callback_query.message, Message):
        return

    selection = gpn_service.get_stations_for_group(callback_data.group_key)
    if selection is None:
        with contextlib.suppress(TelegramBadRequest):
            await callback_query.message.edit_text(
                "⌛ <b>Данные обновились</b>\n\nВыполните команду /fuel ещё раз.",
                reply_markup=DISMISS_KEYBOARD,
            )
        return

    oil_names, stations = selection
    with contextlib.suppress(TelegramBadRequest):
        await callback_query.message.edit_text(
            build_fuel_stations_message(callback_data.group_key, oil_names, stations),
            reply_markup=DISMISS_KEYBOARD,
        )


async def dismiss_gpn_notification(callback_query: CallbackQuery) -> None:
    await callback_query.answer()
    if isinstance(callback_query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await callback_query.message.delete()


def build_fuel_keyboard(fuel_groups: dict[str, tuple[str, ...]]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=f"⛽ {group_key}", callback_data=GpnFuelCallback(group_key=group_key).pack())
        for group_key in fuel_groups
    ]
    rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_availability_message(notifications: list[FuelAvailability]) -> str:
    station_blocks = []
    for notification in notifications:
        station = notification.station
        oils = ", ".join(html.escape(oil) for oil in notification.oils)
        station_blocks.append(
            f'📍 <b><a href="{build_2gis_url(station)}">{html.escape(station.address)}</a></b>\n🔥 В наличии: {oils}'
        )

    stations = "\n\n".join(station_blocks)
    return f"⛽️ <b>На заправках появилось топливо!</b>\n\n{stations}\n\nМожно ехать заправляться 🚗💨"


def build_fuel_stations_message(group_key: str, oil_names: tuple[str, ...], stations: list[Station]) -> str:
    if not stations:
        return f"⛽️ <b>Топливо {html.escape(group_key)}</b>\n\nСейчас его нет ни на одной АЗС."

    station_lines = []
    for station in stations:
        available_names = ", ".join(
            html.escape(oil_name) for oil_name in oil_names if station.oils.get(oil_name, False)
        )
        station_lines.append(
            f'📍 <a href="{build_2gis_url(station)}"><b>{html.escape(station.address)}</b></a>\n🔥 {available_names}'
        )

    return f"⛽️ <b>Где есть топливо {html.escape(group_key)}</b>\n\n" + "\n\n".join(station_lines)


def build_2gis_url(station: Station) -> str:
    coordinates = quote(f"{station.longitude},{station.latitude}")
    return f"https://2gis.ru/?m={coordinates}%2F17&traffic"
