from pydantic import BaseModel


class Station(BaseModel):
    id: int
    city: str
    address: str
    oils: dict[str, bool]


class FuelAvailability(BaseModel):
    station: Station
    oils: tuple[str, ...]
