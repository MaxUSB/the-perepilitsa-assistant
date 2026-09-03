import httpx

from src.core.gpn import REQUEST_BODY, REQUEST_HEADERS, Station


class GpnClient:
    def __init__(
        self,
        *,
        url: str,
        request_timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=url,
            headers=REQUEST_HEADERS,
            timeout=request_timeout_seconds,
            transport=transport,
        )

    async def get_city_stations(self, city: str) -> list[Station]:
        response = await self._client.post("/api/stations/list", json=REQUEST_BODY)
        response.raise_for_status()
        data = response.json()

        oil_names_map = {str(oil_product["id"]): oil_product["shortTitle"] for oil_product in data["oilProducts"]}

        return [
            Station(
                id=station["GPNAZSID"],
                city=station["city"],
                address=station["address"],
                oils=dict(
                    sorted(
                        ((oil_names_map[k], v) for k, v in station["oils"].items()),
                        key=lambda item: item[0],
                    )
                ),
            )
            for station in data["stations"]
            if station["city"] == city
        ]

    async def close(self) -> None:
        await self._client.aclose()
