from pydantic import BaseModel


class Station(BaseModel):
    id: int
    city: str
    address: str
    latitude: float
    longitude: float
    oils: dict[str, bool | None]


class FuelAvailability(BaseModel):
    station: Station
    oils: tuple[str, ...]
