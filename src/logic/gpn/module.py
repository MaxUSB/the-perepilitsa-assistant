import asyncio
import contextlib
import html
import logging
import re
from urllib.parse import quote

from aiogram import Bot, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.core.gpn import FuelAvailability, GpnConfig, Station
from src.logic.gpn.client import GpnClient

logger = logging.getLogger(__name__)


_DISMISS_CALLBACK_DATA = "gpn:dismiss"
_FUEL_CALLBACK_PREFIX = "gpn:fuel:"
_OCTANE_PATTERN = re.compile(r"(?<!\d)(92|95|98|100)(?!\d)")
_DISMISS_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="👌 Ок", callback_data=_DISMISS_CALLBACK_DATA)]]
)


async def dismiss_gpn_notification(callback_query: CallbackQuery) -> None:
    await callback_query.answer()
    if isinstance(callback_query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await callback_query.message.delete()


class GpnModule:
    def __init__(self, *, bot: Bot, config: GpnConfig) -> None:
        self._router = Router(name="gpn")
        self._bot = bot
        self._config = config
        self._client = (
            GpnClient(url=config.url, request_timeout_seconds=config.request_timeout_seconds)
            if config.url is not None
            else None
        )
        self._state: list[Station] | None = None
        self._task: asyncio.Task[None] | None = None
        self._register_handlers()

    def _register_handlers(self) -> None:
        self._router.message.register(self._handle_fuel_command, Command("fuel"))
        self._router.callback_query.register(
            self._handle_fuel_selection,
            lambda query: query.data is not None and query.data.startswith(_FUEL_CALLBACK_PREFIX),
        )
        self._router.callback_query.register(
            dismiss_gpn_notification,
            lambda query: query.data == _DISMISS_CALLBACK_DATA,
        )

    async def _handle_fuel_command(self, message: Message) -> None:
        with contextlib.suppress(TelegramBadRequest):
            await message.delete()

        if self._state is None:
            await message.answer(
                "⏳ <b>Данные о топливе ещё загружаются</b>\n\nПопробуйте выполнить команду /fuel чуть позже.",
                reply_markup=_DISMISS_KEYBOARD,
            )
            return

        fuel_groups = self._get_fuel_groups(self._state)
        if not fuel_groups:
            await message.answer("⛽️ <b>Данные о топливе не найдены</b>", reply_markup=_DISMISS_KEYBOARD)
            return

        await message.answer(
            "⛽️ <b>Какое топливо вас интересует?</b>",
            reply_markup=self._build_fuel_keyboard(fuel_groups),
        )

    async def _handle_fuel_selection(self, callback_query: CallbackQuery) -> None:
        await callback_query.answer()
        if not isinstance(callback_query.message, Message) or callback_query.data is None:
            return

        group_key = callback_query.data.removeprefix(_FUEL_CALLBACK_PREFIX)
        stations = self._state or []
        fuel_groups = self._get_fuel_groups(stations)
        oil_names = fuel_groups.get(group_key)
        if oil_names is None:
            with contextlib.suppress(TelegramBadRequest):
                await callback_query.message.edit_text(
                    "⌛ <b>Данные обновились</b>\n\nВыполните команду /fuel ещё раз.",
                    reply_markup=_DISMISS_KEYBOARD,
                )
            return

        matching_stations = [
            station for station in stations if any(station.oils.get(oil_name, False) for oil_name in oil_names)
        ]
        with contextlib.suppress(TelegramBadRequest):
            await callback_query.message.edit_text(
                self._build_fuel_stations_message(group_key, oil_names, matching_stations),
                reply_markup=_DISMISS_KEYBOARD,
            )

    def router(self) -> Router:
        return self._router

    async def startup(self) -> None:
        if self._client is None:
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

        if self._client is not None:
            await self._client.close()

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
        if self._client is None:
            return

        new_state = await self._client.get_city_stations("Тюмень")
        previous_state = self._state
        self._state = new_state

        if previous_state is None:
            return

        notifications = self._find_newly_available_fuels(previous_state, new_state)
        if not notifications:
            return

        message = self._build_message(notifications)
        for recipient_id in self._config.recipient_ids:
            try:
                await self._bot.send_message(
                    chat_id=recipient_id,
                    text=message,
                    reply_markup=_DISMISS_KEYBOARD,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Failed to send GPN notification to chat %s", recipient_id)

    @staticmethod
    def _find_newly_available_fuels(previous_state: list[Station], new_state: list[Station]) -> list[FuelAvailability]:
        previous_stations = {station.id: station for station in previous_state}
        notifications: list[FuelAvailability] = []

        for station in new_state:
            previous_station = previous_stations.get(station.id)
            if previous_station is None:
                continue

            appeared_oils = tuple(
                oil_name
                for oil_name, is_available in station.oils.items()
                if is_available and previous_station.oils.get(oil_name) is False
            )
            if appeared_oils:
                notifications.append(FuelAvailability(station=station, oils=appeared_oils))

        return notifications

    @classmethod
    def _build_message(cls, notifications: list[FuelAvailability]) -> str:
        station_blocks = []
        for notification in notifications:
            station = notification.station
            oils = ", ".join(html.escape(oil) for oil in notification.oils)
            station_blocks.append(
                f'📍 <b><a href="{cls._build_2gis_url(station)}">{html.escape(station.address)}</a></b>\n'
                f"🔥 В наличии: {oils}"
            )

        stations = "\n\n".join(station_blocks)
        return f"⛽️ <b>На заправках появилось топливо!</b>\n\n{stations}\n\nМожно ехать заправляться 🚗💨"

    @staticmethod
    def _get_fuel_groups(stations: list[Station]) -> dict[str, tuple[str, ...]]:
        groups: dict[str, set[str]] = {}
        for station in stations:
            for oil_name in station.oils:
                match = _OCTANE_PATTERN.search(oil_name)
                group_key = match.group(1) if match is not None else oil_name
                groups.setdefault(group_key, set()).add(oil_name)

        return {key: tuple(sorted(oils)) for key, oils in sorted(groups.items())}

    @staticmethod
    def _build_fuel_keyboard(fuel_groups: dict[str, tuple[str, ...]]) -> InlineKeyboardMarkup:
        buttons = [
            InlineKeyboardButton(text=f"⛽ {group_key}", callback_data=f"{_FUEL_CALLBACK_PREFIX}{group_key}")
            for group_key in fuel_groups
        ]
        rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
        return InlineKeyboardMarkup(inline_keyboard=rows)

    @classmethod
    def _build_fuel_stations_message(
        cls,
        group_key: str,
        oil_names: tuple[str, ...],
        stations: list[Station],
    ) -> str:
        if not stations:
            return f"⛽️ <b>Топливо {html.escape(group_key)}</b>\n\nСейчас его нет ни на одной АЗС."

        station_lines = []
        for station in stations:
            available_names = ", ".join(
                html.escape(oil_name) for oil_name in oil_names if station.oils.get(oil_name, False)
            )
            station_lines.append(
                f'📍 <a href="{cls._build_2gis_url(station)}"><b>{html.escape(station.address)}</b></a>'
                f"\n🔥 {available_names}"
            )

        return f"⛽️ <b>Где есть топливо {html.escape(group_key)}</b>\n\n" + "\n\n".join(station_lines)

    @staticmethod
    def _build_2gis_url(station: Station) -> str:
        coordinates = quote(f"{station.longitude},{station.latitude}")
        return f"https://2gis.ru/tyumen?m={coordinates}%2F17&traffic"
