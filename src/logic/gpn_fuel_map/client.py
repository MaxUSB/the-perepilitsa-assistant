import httpx


class GpnFuelMapClient:
    def __init__(self, *, url: str, request_timeout_seconds: float) -> None:
        self._url = url
        self._timeout = request_timeout_seconds

    async def get_fuel_map(self) -> list:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._url}/api/stations/list",
                cookies={
                    "csrf-token-name": "csrftoken; Max-Age=600; Path=/; secure",
                    "csrf-token-value": "18d1e5d50e01cc5a521d2948ccc4a105175ce96360aa88779462e110df3598663f2d184c1a2d8a10; Max-Age=600; Path=/; secure",
                    "session-cookie": "18d1d9d78d9e6fd18fd4ef4d6940ac72361bdd108c6a0e3b94cf6248f3ac1334d37b5aa8a9b03c3b2f91f4e6ef54a312; Path=/; Secure; HttpOnly;",
                },
                json={
                    "open": False,
                    "wash": False,
                    "AZSShopTypeID": False,
                    "services": {"car": {}, "payment": {}, "person": {}, "station": {}},
                },
            )
            response.raise_for_status()
            return response.json()
