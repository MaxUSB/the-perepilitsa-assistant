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
