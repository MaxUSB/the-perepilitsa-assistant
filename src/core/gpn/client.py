from typing import Protocol

from src.core.gpn.models import Station


class GpnClient(Protocol):
    async def get_city_stations(self, city: str) -> list[Station]: ...

    async def close(self) -> None: ...
