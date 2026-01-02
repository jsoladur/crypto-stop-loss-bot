import logging
from typing import Self

from pytest_httpserver import RequestMatcher, URIPattern
from werkzeug import Request

logger = logging.getLogger(__name__)


class MEXCContractRequestMatcher(RequestMatcher):
    def set_api_key_and_secret(self, api_key: str, api_secret: str) -> Self:
        self._api_key = api_key
        self._api_secret = api_secret
        return self

    def difference(self, request: Request) -> list[tuple[str, str, str | URIPattern]]:
        if not self._api_key or not self._api_secret:
            raise ValueError("MEXC API key and/or secret are not setup!")

        difference = super().difference(request)
        # Check API key, nonce, signature
        if (received_api_key := request.headers.get("ApiKey")) != self._api_key:
            difference.append(("ApiKey", received_api_key, self._api_key))
        if (received_timestamp := request.headers.get("Request-Time")) is None:
            difference.append(("Request-Time", received_timestamp, ""))
        if (signature := request.headers.get("Signature")) is None:
            difference.append(("Signature", signature, ""))
        return difference
