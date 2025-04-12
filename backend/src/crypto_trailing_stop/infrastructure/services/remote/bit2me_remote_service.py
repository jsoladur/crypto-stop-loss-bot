from crypto_trailing_stop.config import get_configuration_properties
from httpx import AsyncClient
from typing import Any
from crypto_trailing_stop.infrastructure.adapters.remote.base import (
    AbstractHttpRemoteAsyncService,
)


class Bit2MeRemoteService(AbstractHttpRemoteAsyncService):
    def __init__(self):
        self._configuration_properties = get_configuration_properties()
        self._base_url = self._configuration_properties.bit2me_api_base_url
        self._api_key = self._configuration_properties.bit2me_api_key

    async def get_sell_orders(
        self, *, client: AsyncClient | None = None
    ) -> dict[str, Any]:
        response = await self._perform_http_request(url="/api/v1/orders", client=client)
        response.raise_for_status()
        json_response = response.json()
        return json_response

    async def _apply_interceptor(
        self,
        *,
        method: str = "GET",
        url: str = "/",
        params: dict[str, Any] | None = {},
        headers: dict[str, Any] | None = {},
    ) -> tuple[str, str, dict[str, Any] | None, dict[str, Any] | None]:
        params, headers = super()._apply_interceptor(
            method=method, url=url, params=params, headers=headers
        )

    async def get_http_client(self) -> AsyncClient:
        return AsyncClient(
            base_url=self._base_url, headers={"X-API-KEY", self._api_key}
        )
