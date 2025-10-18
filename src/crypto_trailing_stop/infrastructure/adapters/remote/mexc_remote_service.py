import base64
import hashlib
import hmac
import json
import logging
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import backoff
from httpx import URL, AsyncClient, HTTPStatusError, NetworkError, Response, Timeout, TimeoutException
from pandas import Timedelta

from crypto_trailing_stop.commons.constants import MEXC_RETRYABLE_HTTP_STATUS_CODES
from crypto_trailing_stop.commons.utils import backoff_on_backoff_handler, prepare_backoff_giveup_handler_fn
from crypto_trailing_stop.config.configuration_properties import ConfigurationProperties
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_account_info_dto import Bit2MeAccountInfoDto
from crypto_trailing_stop.infrastructure.adapters.remote.base import AbstractHttpRemoteAsyncService

if TYPE_CHECKING:
    from crypto_trailing_stop.infrastructure.tasks.vo.types import Timeframe

logger = logging.getLogger(__name__)


class MEXCRemoteService(AbstractHttpRemoteAsyncService):
    def __init__(self, configuration_properties: ConfigurationProperties) -> None:
        self._configuration_properties = configuration_properties
        self._base_url = str(self._configuration_properties.bit2me_api_base_url)
        self._api_key = self._configuration_properties.mexc_api_key
        self._api_secret = self._configuration_properties.mexc_api_secret
        if not self._base_url or not self._api_key or not self._api_secret:
            raise ValueError("MEXC API configuration is missing or incomplete.")

    async def get_account_info(self, *, client: AsyncClient | None = None) -> Bit2MeAccountInfoDto:
        response = await self._perform_http_request(url="/v1/account", client=client)
        ret = Bit2MeAccountInfoDto.model_validate_json(response.content)
        return ret

    async def get_http_client(self) -> AsyncClient:
        return AsyncClient(
            base_url=self._base_url, headers={"X-API-KEY": self._api_key}, timeout=Timeout(10, connect=5, read=60)
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
        params: dict[str, Any] | None = {},
        headers: dict[str, Any] | None = {},
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
        params: dict[str, Any] | None = {},
        headers: dict[str, Any] | None = {},
        body: Any | None = None,
    ) -> tuple[str, str, dict[str, Any] | None, dict[str, Any] | None]:
        params, headers = await super()._apply_request_interceptor(
            method=method, url=url, params=params, headers=headers, body=body
        )
        nonce = headers["x-nonce"] = str(int(time.time() * 1000))  # UTC timestamp in milliseconds
        headers["api-signature"] = await self._generate_api_signature(nonce, url, params, body)
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
        try:
            response.raise_for_status()
            return await super()._apply_response_interceptor(
                method=method, url=url, params=params, headers=headers, body=body, response=response
            )
        except HTTPStatusError as e:
            raise ValueError(
                f"Bit2Me API error: HTTP {method} {self._build_full_url(url, params)} "
                + f"- Status code: {response.status_code} - {response.text}",
                response,
            ) from e

    async def _generate_api_signature(self, nonce: str, url: str, params: dict[str, Any] | None, body: Any) -> str:
        url = self._build_full_url(url, params)
        message_to_sign = f"{nonce}:{url}"
        if body:  # pragma: no cover
            message_to_sign += f":{json.dumps(body, separators=(',', ':'))}"
        sha256_hash = hashlib.sha256()
        hash_digest = sha256_hash.update(message_to_sign.encode("utf-8"))
        hash_digest = sha256_hash.digest()
        # Create HMAC-SHA512
        hmac_obj = hmac.new(self._api_secret.encode(), hash_digest, hashlib.sha512)
        hmac_digest = base64.b64encode(hmac_obj.digest()).decode()
        return hmac_digest

    def _convert_timeframe_to_interval(self, timeframe: "Timeframe") -> int:
        # The interval of entries in minutes: 1, 5, 15, 30, 60 (1 hour), 240 (4 hours), 1440 (1 day)
        td = Timedelta(timeframe)
        ret = int(td.total_seconds() // 60)
        return ret

    def _build_full_url(self, path: str, query_params: dict[str, any]) -> str:
        full_url = path
        if query_params:
            query_string = urlencode(query_params, doseq=True)
            full_url += "?" + query_string
        return full_url
