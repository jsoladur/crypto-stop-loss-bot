import hashlib
import hmac
import json
import logging
import time
from typing import Any
from urllib.parse import urlencode

import backoff
import cachebox
from httpx import URL, AsyncClient, HTTPStatusError, NetworkError, Response, Timeout, TimeoutException
from pydantic import RootModel

from crypto_trailing_stop.commons.constants import (
    DEFAULT_IN_MEMORY_CACHE_TTL_IN_SECONDS,
    MEXC_RETRYABLE_HTTP_STATUS_CODES,
)
from crypto_trailing_stop.commons.utils import backoff_on_backoff_handler, prepare_backoff_giveup_handler_fn
from crypto_trailing_stop.config.configuration_properties import ConfigurationProperties
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_account_info_dto import MEXCAccountInfoDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_exchange_info_dto import MEXCExchangeInfoDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_ticker_book_dto import MEXCTickerBookDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_ticker_price_dto import MEXCTickerPriceDto
from crypto_trailing_stop.infrastructure.adapters.remote.base import AbstractHttpRemoteAsyncService

logger = logging.getLogger(__name__)


class MEXCRemoteService(AbstractHttpRemoteAsyncService):
    def __init__(self, configuration_properties: ConfigurationProperties) -> None:
        self._configuration_properties = configuration_properties
        self._base_url = str(self._configuration_properties.mexc_api_base_url)
        self._api_key = self._configuration_properties.mexc_api_key
        self._api_secret = self._configuration_properties.mexc_api_secret
        if not self._base_url or not self._api_key or not self._api_secret:
            raise ValueError("MEXC API configuration is missing or incomplete.")

    async def get_account_info(self, *, client: AsyncClient | None = None) -> MEXCAccountInfoDto:
        response = await self._perform_http_request(url="/api/v3/account", client=client)
        ret = MEXCAccountInfoDto.model_validate_json(response.content)
        return ret

    async def get_ticker_price(self, symbol: str, *, client: AsyncClient | None = None) -> MEXCTickerPriceDto:
        response = await self._perform_http_request(
            url="/api/v3/ticker/price", params={"symbol": symbol}, client=client
        )
        ret = MEXCTickerPriceDto.model_validate_json(response.content)
        return ret

    async def get_ticker_book(self, symbol: str, *, client: AsyncClient | None = None) -> MEXCTickerBookDto:
        response = await self._perform_http_request(
            url="/api/v3/ticker/bookTicker", params={"symbol": symbol}, client=client
        )
        ret = MEXCTickerBookDto.model_validate_json(response.content)
        return ret

    async def get_ticker_book_list(self, client: AsyncClient | None = None) -> list[MEXCTickerBookDto]:
        response = await self._perform_http_request(url="/api/v3/ticker/bookTicker", client=client)
        ret = RootModel[list[MEXCTickerBookDto]].model_validate_json(response.content).root
        return ret

    async def get_ticker_price_list(self, client: AsyncClient | None = None) -> list[MEXCTickerPriceDto]:
        response = await self._perform_http_request(url="/api/v3/ticker/price", client=client)
        ret = RootModel[list[MEXCTickerPriceDto]].model_validate_json(response.content).root
        return ret

    @cachebox.cachedmethod(
        cachebox.TTLCache(0, ttl=DEFAULT_IN_MEMORY_CACHE_TTL_IN_SECONDS), key_maker=lambda _, __: "mexc_exchange_info"
    )
    async def get_exchange_info(self, *, client: AsyncClient | None = None) -> MEXCExchangeInfoDto:
        response = await self._perform_http_request(url="/api/v3/exchangeInfo", client=client)
        ret = MEXCExchangeInfoDto.model_validate_json(response.content)
        return ret

    async def get_http_client(self) -> AsyncClient:
        return AsyncClient(
            base_url=self._base_url, headers={"X-MEXC-APIKEY": self._api_key}, timeout=Timeout(10, connect=5, read=30)
        )

    @backoff.on_exception(
        backoff.fibo,
        exception=(ValueError, NetworkError, TimeoutException),
        max_value=5,
        max_tries=7,
        jitter=backoff.random_jitter,
        giveup=prepare_backoff_giveup_handler_fn(MEXC_RETRYABLE_HTTP_STATUS_CODES),
        on_backoff=backoff_on_backoff_handler,
    )
    async def _perform_http_request(
        self,
        *,
        method: str = "GET",
        url: URL | str = "/",
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
        body: Any | None = None,
        client: AsyncClient = None,
        **kwargs,
    ) -> Response:
        response = await super()._perform_http_request(
            method=method, url=url, params=params, headers=headers, body=body, client=client, **kwargs
        )
        return response

    async def _apply_request_interceptor(
        self,
        *,
        method: str = "GET",
        url: str = "/",
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
        body: Any | None = None,
    ) -> tuple[str, str, dict[str, Any] | None, dict[str, Any] | None]:
        params, headers = await super()._apply_request_interceptor(
            method=method, url=url, params=params, headers=headers, body=body
        )
        params["timestamp"] = str(int(time.time() * 1000))  # UTC timestamp in milliseconds
        params["signature"] = await self._generate_signature_query_param(params, body)
        return params, headers

    async def _apply_response_interceptor(
        self,
        *,
        method: str = "GET",
        url: str = "/",
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
        body: Any | None = None,
        response: Response,
    ) -> Response:
        params = params or {}
        headers = headers or {}
        try:
            response.raise_for_status()
            return await super()._apply_response_interceptor(
                method=method, url=url, params=params, headers=headers, body=body, response=response
            )
        except HTTPStatusError as e:
            raise ValueError(
                f"MEXC API error: HTTP {method} {self._build_full_url(url, params)} "
                + f"- Status code: {response.status_code} - {response.text}",
                response,
            ) from e

    async def _generate_signature_query_param(self, params: dict[str, Any] | None, body: Any) -> str:
        if body:  # pragma: no cover
            params.update(json.loads(body) if isinstance(body, str) else body)
        query_string = urlencode(params, doseq=True)
        signature = hmac.new(self._api_secret.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256).hexdigest()
        return signature
