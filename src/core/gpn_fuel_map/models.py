from pydantic import BaseModel


class Station(BaseModel):
    id: int
    city: str
    address: str
    oils: dict[str, bool]
