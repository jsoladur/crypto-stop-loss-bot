from crypto_trailing_stop.config import get_configuration_properties
from httpx import AsyncClient
from typing import Any
from backend.src.crypto_trailing_stop.infrastructure.services.remote.base import (
    AbstractHttpRemoteAsyncService,
)


class Bit2MeRemoteService(AbstractHttpRemoteAsyncService):
    def __init__(self):
        self._configuration_properties = get_configuration_properties()
        self._base_url = self._configuration_properties.bit2me_api_base_url
        self._api_key = self._configuration_properties.bit2me_api_key

    def get_sell_orders(self, *, client: AsyncClient | None = None) -> dict[str, Any]:
        raise NotImplementedError("Not implemented")

    async def get_http_client(self) -> AsyncClient:
        return AsyncClient(
            base_url=self._base_url, headers={"X-API-KEY", self._api_key}
        )
