import time
from crypto_trailing_stop.config import get_configuration_properties
from httpx import AsyncClient, Response, Timeout
from typing import Any
from crypto_trailing_stop.infrastructure.adapters.remote.base import (
    AbstractHttpRemoteAsyncService,
)
from enum import Enum
from urllib.parse import urlencode
from pydantic import RootModel
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_account_info_dto import (
    Bit2MeAccountInfoDto,
)
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_porfolio_balance_dto import (
    Bit2MePortfolioBalanceDto,
)
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import (
    Bit2MeOrderDto,
    CreateNewBit2MeOrderDto,
    Bit2MeOrderStatus,
    Bit2MeOrderSide,
    Bit2MeOrderType,
)
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import (
    Bit2MeTickersDto,
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

    async def get_favourite_crypto_currencies(
        self, *, client: AsyncClient | None = None
    ) -> list[str]:
        response = await self._perform_http_request(
            url="/v1/currency-favorites/favorites",
            client=client,
        )
        response.raise_for_status()
        favourite_crypto_currencies = [
            favourite_currency["currency"] for favourite_currency in response.json()
        ]
        return favourite_crypto_currencies

    async def get_account_info(
        self, *, client: AsyncClient | None = None
    ) -> Bit2MeAccountInfoDto:
        response = await self._perform_http_request(
            url="/v1/account",
            client=client,
        )
        response.raise_for_status()
        ret = Bit2MeAccountInfoDto.model_validate_json(response.content)
        return ret

    async def retrieve_porfolio_balance(
        self, user_currency: str, *, client: AsyncClient | None = None
    ) -> list[Bit2MePortfolioBalanceDto]:
        response = await self._perform_http_request(
            url="/v1/portfolio/balance",
            params={"userCurrency": user_currency.strip().upper()},
            client=client,
        )
        response.raise_for_status()  # Ensure we raise an error for bad responses
        ret = (
            RootModel[list[Bit2MePortfolioBalanceDto]]
            .model_validate_json(response.content)
            .root
        )
        return ret

    async def get_accounting_summary_by_year(
        self, year: str, *, client: AsyncClient | None = None
    ) -> bytes:
        response = await self._perform_http_request(
            url=f"/v1/accounting/summary/{year}",
            params={
                "timeZone": "Europe/Madrid",
                "langCode": "en",
                "documentType": "xlsx",
            },
            client=client,
        )
        response.raise_for_status()  # Ensure we raise an error for bad responses
        return response.content

    async def get_tickers_by_symbol(
        self, symbol: str, *, client: AsyncClient | None = None
    ) -> Bit2MeTickersDto | None:
        response = await self._perform_http_request(
            url="/v2/trading/tickers", params={"symbol": symbol}, client=client
        )
        tickers = (
            RootModel[list[Bit2MeTickersDto]].model_validate_json(response.content).root
        )
        ret: Bit2MeTickersDto | None = None
        if tickers:
            ret, *_ = tickers
        return ret

    async def get_pending_stop_limit_orders(
        self,
        *,
        side: Bit2MeOrderSide | None = None,
        client: AsyncClient | None = None,
    ) -> list[Bit2MeOrderDto]:
        return await self.get_orders(
            side=side,
            status=["open", "inactive"],
            order_type="stop-limit",
            client=client,
        )

    async def get_pending_buy_orders(
        self,
        *,
        order_type: Bit2MeOrderType | None = None,
        client: AsyncClient | None = None,
    ) -> list[Bit2MeOrderDto]:
        return await self.get_orders(
            side="buy",
            order_type=order_type,
            status=["open", "inactive"],
            client=client,
        )

    async def get_orders(
        self,
        *,
        side: Bit2MeOrderSide | None = None,
        order_type: Bit2MeOrderType | None = None,
        status: list[Bit2MeOrderStatus] | Bit2MeOrderStatus | None = None,
        client: AsyncClient | None = None,
    ) -> list[Bit2MeOrderDto]:
        status = status or []
        status = (
            status if isinstance(status, (list, set, tuple, frozenset)) else [status]
        )
        params = {"direction": "desc"}
        if status:
            params["status_in"] = ",".join(
                [s.value if isinstance(s, Enum) else str(s) for s in status]
            )
        if side:
            params["side"] = side
        if order_type:
            params["orderType"] = order_type
        response = await self._perform_http_request(
            url="/v1/trading/order",
            params=params,
            client=client,
        )
        orders: list[Bit2MeOrderDto] = (
            RootModel[list[Bit2MeOrderDto]].model_validate_json(response.content).root
        )
        return orders

    async def create_order(
        self, order: CreateNewBit2MeOrderDto, *, client: AsyncClient | None = None
    ) -> None:
        order_as_dict: dict[str, Any] = order.model_dump(
            mode="json", by_alias=True, exclude_none=True
        )
        response = await self._perform_http_request(
            method="POST",
            url="/v1/trading/order",
            body=order_as_dict,
            client=client,
        )
        order = Bit2MeOrderDto.model_validate_json(response.content)
        return order

    async def cancel_order_by_id(
        self, id: str, *, client: AsyncClient | None = None
    ) -> None:
        await self._perform_http_request(
            method="DELETE",
            url=f"/v1/trading/order/{id}",
            client=client,
        )

    async def _apply_request_interceptor(
        self,
        *,
        method: str = "GET",
        url: str = "/",
        params: dict[str, Any] | None = {},
        headers: dict[str, Any] | None = {},
        body: Any | None = None,
    ) -> tuple[str, str, dict[str, Any] | None, dict[str, Any] | None]:
        params, headers = await super()._apply_request_interceptor(
            method=method, url=url, params=params, headers=headers, body=body
        )
        nonce = headers["x-nonce"] = str(
            int(time.time() * 1000)
        )  # UTC timestamp in milliseconds
        headers["api-signature"] = await self._generate_api_signature(
            nonce, url, params, body
        )
        return params, headers

    async def _apply_response_interceptor(
        self,
        *,
        method: str = "GET",
        url: str = "/",
        params: dict[str, Any] | None = {},
        headers: dict[str, Any] | None = {},
        body: Any | None = None,
        response: Response,
    ) -> Response:
        if not response.is_success:
            raise ValueError(
                f"Bit2Me API error: HTTP {method} {self._build_full_url(url, params)} "
                + f"- Status code: {response.status_code} - {response.text}"
            )
        return await super()._apply_response_interceptor(
            method=method,
            url=url,
            params=params,
            headers=headers,
            body=body,
            response=response,
        )

    async def get_http_client(self) -> AsyncClient:
        return AsyncClient(
            base_url=self._base_url,
            headers={"X-API-KEY": self._api_key},
            timeout=Timeout(10, connect=5, read=60),
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
            message_to_sign += f":{json.dumps(body, separators=(',', ':'))}"
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
            query_string = urlencode(query_params, doseq=True)
            full_url += "?" + query_string
        return full_url
