import base64
import hashlib
import hmac
import logging
from typing import Self

from pytest_httpserver import RequestMatcher, URIPattern
from werkzeug import Request

logger = logging.getLogger(__name__)


class Bit2MeAPIRequestMatcher(RequestMatcher):
    def set_bit2me_api_key_and_secret(self, bit2me_api_key: str, bit2me_api_secret: str) -> Self:
        self._bit2me_api_key = bit2me_api_key
        self._bit2me_api_secret = bit2me_api_secret
        return self

    def difference(self, request: Request) -> list[tuple[str, str, str | URIPattern]]:
        if not self._bit2me_api_key or not self._bit2me_api_secret:
            raise ValueError("Bit2Me API key and/or secret are not setup!")

        difference = super().difference(request)
        # Check API key, nonce, signature
        if (received_api_key := request.headers.get("X-API-KEY")) != self._bit2me_api_key:
            difference.append(("X-API-KEY", received_api_key, self._bit2me_api_key))
        if (received_nonce := request.headers.get("x-nonce")) is None:
            difference.append(("x-nonce", received_nonce, ""))
        if not self._match_api_signature(request):
            difference.append(
                ("api-signature", request.headers.get("api-signature"), self._generate_api_signature(request))
            )

        return difference

    def _match_api_signature(self, request: Request) -> bool:
        expected_api_signature = self._generate_api_signature(request)
        api_signature_header = request.headers.get("api-signature")
        ret = expected_api_signature == api_signature_header
        return ret

    def _generate_api_signature(self, request: Request) -> str:
        x_nonce = request.headers["x-nonce"]
        full_path = (request.full_path if request.query_string else request.path).removeprefix("/bit2me-api")
        message_to_sign = f"{x_nonce}:{full_path}"
        raw_body = request.get_data()
        if raw_body:
            message_to_sign += f":{raw_body.decode()}"
        sha256_hash = hashlib.sha256()
        hash_digest = sha256_hash.update(message_to_sign.encode("utf-8"))
        hash_digest = sha256_hash.digest()
        # Create HMAC-SHA512
        hmac_obj = hmac.new(self._bit2me_api_secret.encode(), hash_digest, hashlib.sha512)
        hmac_digest = base64.b64encode(hmac_obj.digest()).decode()
        return hmac_digest
