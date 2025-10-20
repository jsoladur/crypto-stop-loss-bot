import hashlib
import hmac
import json
import logging
from typing import Self
from urllib.parse import parse_qsl, urlencode

from pytest_httpserver import RequestMatcher, URIPattern
from werkzeug import Request
from werkzeug.datastructures import MultiDict

logger = logging.getLogger(__name__)


class MEXCAPIRequestMatcher(RequestMatcher):
    def set_api_key_and_secret(self, api_key: str, api_secret: str) -> Self:
        self._api_key = api_key
        self._api_secret = api_secret
        return self

    def difference(self, request: Request) -> list[tuple[str, str, str | URIPattern]]:
        if not self._api_key or not self._api_secret:
            raise ValueError("MEXC API key and/or secret are not setup!")

        difference = super().difference(request)
        # Check API key, nonce, signature
        if (received_api_key := request.headers.get("X-MEXC-APIKEY")) != self._api_key:
            difference.append(("X-MEXC-APIKEY", received_api_key, self._api_key))

        query_params: dict[str, str] = MultiDict(parse_qsl(request.query_string.decode("utf-8"))).to_dict()
        if (received_timestamp := query_params.get("timestamp")) is None:
            difference.append(("timestamp", received_timestamp, ""))
        if not self._match_api_signature(request, query_params):
            difference.append(
                ("signature", query_params.get("signature"), self._generate_api_signature(request, query_params))
            )
        return difference

    def _match_api_signature(self, request: Request, query_params: dict[str, str]) -> bool:
        expected_api_signature = self._generate_api_signature(request, query_params)
        signature_query_parameters = query_params.get("signature")
        ret = expected_api_signature == signature_query_parameters
        return ret

    def _generate_api_signature(self, request: Request, query_params: dict[str, str]) -> str:
        params_to_sign = {key: value for key, value in query_params.items() if key != "signature"}
        raw_body = request.get_data()
        if raw_body:
            params_to_sign.update(json.loads(raw_body.decode()))
        query_string_to_sign = urlencode(params_to_sign, doseq=True)
        signature = hmac.new(
            self._api_secret.encode("utf-8"), query_string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return signature
