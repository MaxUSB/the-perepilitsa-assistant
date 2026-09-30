import asyncio
import re
from datetime import UTC, datetime

from src.core.gpn import FuelAvailability, GpnClient, Station
from src.logic.gpn.store import GpnStateStore, GpnSubscriptionStore

_OCTANE_PATTERN = re.compile(r"(?<!\d)(92|95|98|100)(?!\d)")


class GpnService:
    def __init__(
        self, *, city: str, client: GpnClient | None, store: GpnStateStore, subscriptions: GpnSubscriptionStore
    ) -> None:
        self._city = city
        self._client = client
        self._store = store
        self._subscriptions_store = subscriptions
        self._subscriptions: dict[int, set[str]] = {}
        self._subscription_lock = asyncio.Lock()
        self._state: list[Station] | None = None
        self.updated_at: datetime | None = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    async def restore(self) -> list[Station] | None:
        self._subscriptions = await asyncio.to_thread(self._subscriptions_store.load)
        restored_state = await asyncio.to_thread(self._store.load)
        self._state = (
            restored_state
            if restored_state is None or all(station.city == self._city for station in restored_state)
            else None
        )
        if self._state is not None:
            timestamp = await asyncio.to_thread(self._store.updated_at)
            self.updated_at = datetime.fromtimestamp(timestamp, tz=UTC) if timestamp is not None else None
        return self._state

    async def refresh(self) -> list[FuelAvailability]:
        if self._client is None:
            return []

        new_state = await self._client.get_city_stations(self._city)
        previous_state = self._state
        await asyncio.to_thread(self._store.save, new_state)
        self._state = new_state
        self.updated_at = datetime.now(UTC)

        if previous_state is None:
            return []
        return self._find_newly_available_fuels(previous_state, new_state)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()

    def get_fuel_groups(self) -> dict[str, tuple[str, ...]] | None:
        if self._state is None:
            return None

        groups: dict[str, set[str]] = {}
        for station in self._state:
            for oil_name in station.oils:
                match = _OCTANE_PATTERN.search(oil_name)
                group_key = match.group(1) if match is not None else oil_name
                groups.setdefault(group_key, set()).add(oil_name)

        return {key: tuple(sorted(oils)) for key, oils in sorted(groups.items())}

    def subscribed_groups(self, user_id: int) -> frozenset[str]:
        return frozenset(self._subscriptions.get(user_id, set()))

    async def toggle_subscription(self, user_id: int, group_key: str) -> bool | None:
        async with self._subscription_lock:
            if group_key not in (self.get_fuel_groups() or {}):
                return None
            updated = {key: value.copy() for key, value in self._subscriptions.items()}
            groups = updated.setdefault(user_id, set())
            if group_key in groups:
                groups.remove(group_key)
            else:
                groups.add(group_key)
            if not groups:
                del updated[user_id]
            await asyncio.to_thread(self._subscriptions_store.save, updated)
            self._subscriptions = updated
            return group_key in groups

    def notifications_for_user(self, user_id: int, notifications: list[FuelAvailability]) -> list[FuelAvailability]:
        groups = self.subscribed_groups(user_id)
        return [
            FuelAvailability(
                station=notification.station,
                oils=tuple(oil for oil in notification.oils if self._group_key(oil) in groups),
            )
            for notification in notifications
            if any(self._group_key(oil) in groups for oil in notification.oils)
        ]

    @staticmethod
    def _group_key(oil_name: str) -> str:
        match = _OCTANE_PATTERN.search(oil_name)
        return match.group(1) if match is not None else oil_name

    def get_stations_for_group(self, group_key: str) -> tuple[tuple[str, ...], list[Station]] | None:
        fuel_groups = self.get_fuel_groups()
        if fuel_groups is None:
            return None

        oil_names = fuel_groups.get(group_key)
        if oil_names is None:
            return None

        stations = [
            station
            for station in (self._state or [])
            if any(station.oils.get(oil_name, False) for oil_name in oil_names)
        ]
        return oil_names, stations

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
