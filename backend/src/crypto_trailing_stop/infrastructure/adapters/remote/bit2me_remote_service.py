import time
from crypto_trailing_stop.config import get_configuration_properties
from httpx import AsyncClient
from typing import Any
from crypto_trailing_stop.infrastructure.adapters.remote.base import (
    AbstractHttpRemoteAsyncService,
)
from urllib.parse import urlencode
from pydantic import RootModel
from typing import Literal
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import (
    Bit2MeOrderDto,
)
import hashlib
import hmac
import base64
import json


class Bit2MeRemoteService(AbstractHttpRemoteAsyncService):
    def __init__(self):
        self._configuration_properties = get_configuration_properties()
        self._base_url = str(self._configuration_properties.bit2me_api_base_url)
        self._api_key = self._configuration_properties.bit2me_api_key
        self._api_secret = self._configuration_properties.bit2me_api_secret

    async def get_pending_orders(
        self,
        *,
        side: Literal["buy", "sell"] | None = None,
        client: AsyncClient | None = None,
    ) -> list[Bit2MeOrderDto]:
        return await self.get_orders(side=side, status="open", client=client)

    async def get_orders(
        self,
        *,
        side: Literal["buy", "sell"] | None = None,
        status: Literal["open", "filled", "cancelled", "inactive"] | None = None,
        client: AsyncClient | None = None,
    ) -> list[Bit2MeOrderDto]:
        params = {}
        if side:
            params["side"] = side
        if status:
            params["status"] = status
        response = await self._perform_http_request(
            url="/v1/trading/order", params=params, client=client
        )
        if not response.is_success:
            raise ValueError(
                f"Bit2Me API error: {response.status_code} - {response.text}"
            )
        json_response = response.json()
        orders: list[Bit2MeOrderDto] = (
            RootModel[list[Bit2MeOrderDto]].model_validate(json_response).root
        )
        return orders

    async def _apply_interceptor(
        self,
        *,
        method: str = "GET",
        url: str = "/",
        params: dict[str, Any] | None = {},
        headers: dict[str, Any] | None = {},
        body: Any | None = None,
    ) -> tuple[str, str, dict[str, Any] | None, dict[str, Any] | None]:
        params, headers = await super()._apply_interceptor(
            method=method, url=url, params=params, headers=headers, body=body
        )
        nonce = headers["x-nonce"] = str(
            int(time.time() * 1000)
        )  # UTC timestamp in milliseconds
        headers["api-signature"] = await self._generate_api_signature(
            nonce, url, params, body
        )
        return params, headers

    async def get_http_client(self) -> AsyncClient:
        return AsyncClient(
            base_url=self._base_url, headers={"X-API-KEY": self._api_key}
        )

    async def _generate_api_signature(
        self,
        nonce: str,
        url: str,
        params: dict[str, Any] | None,
        body: Any,
    ) -> str:
        url = self._build_full_url(url, params)
        message_to_sign = f"{nonce}:{url}"
        if body:
            message_to_sign += f":{json.dumps(body)}"
        sha256_hash = hashlib.sha256()
        hash_digest = sha256_hash.update(message_to_sign.encode("utf-8"))
        hash_digest = sha256_hash.digest()
        # Create HMAC-SHA512
        hmac_obj = hmac.new(self._api_secret.encode(), hash_digest, hashlib.sha512)
        hmac_digest = base64.b64encode(hmac_obj.digest()).decode()
        return hmac_digest

    def _build_full_url(self, path: str, query_params: dict[str, any]) -> str:
        full_url = path
        if query_params:
            query_string = urlencode(query_params)
            full_url += "?" + query_string
        return full_url
