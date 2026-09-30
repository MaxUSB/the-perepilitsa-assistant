import json
import os
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from src.core.gpn import Station

_STATIONS_ADAPTER = TypeAdapter(list[Station])


class GpnStateStore:
    def __init__(self, state_path: Path) -> None:
        self._state_path = state_path

    def load(self) -> list[Station] | None:
        if not self._state_path.exists():
            return None

        try:
            return _STATIONS_ADAPTER.validate_json(self._state_path.read_bytes())
        except OSError, ValidationError, json.JSONDecodeError:
            return None

    def save(self, stations: list[Station]) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._state_path.with_suffix(f"{self._state_path.suffix}.tmp")
        payload = _STATIONS_ADAPTER.dump_json(stations)

        try:
            with temporary_path.open("wb") as temporary_file:
                temporary_file.write(payload)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, self._state_path)
        finally:
            temporary_path.unlink(missing_ok=True)

    def updated_at(self) -> float | None:
        try:
            return self._state_path.stat().st_mtime
        except OSError:
            return None


class GpnSubscriptionStore:
    def __init__(self, subscriptions_path: Path) -> None:
        self._state_path = subscriptions_path

    def load(self) -> dict[int, set[str]]:
        try:
            data = json.loads(self._state_path.read_text())
            if not isinstance(data, dict) or not all(
                isinstance(key, str)
                and key.isdecimal()
                and isinstance(value, list)
                and all(isinstance(item, str) for item in value)
                for key, value in data.items()
            ):
                return {}
            return {int(key): set(value) for key, value in data.items()}
        except OSError, ValueError, TypeError:
            return {}

    def save(self, subscriptions: dict[int, set[str]]) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._state_path.with_suffix(".json.tmp")
        payload = json.dumps({str(key): sorted(value) for key, value in subscriptions.items()}).encode()
        try:
            with temporary_path.open("wb") as temporary_file:
                temporary_file.write(payload)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, self._state_path)
        finally:
            temporary_path.unlink(missing_ok=True)
