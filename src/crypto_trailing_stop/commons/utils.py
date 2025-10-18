import logging
from collections.abc import Callable
from typing import Any

from httpx import HTTPStatusError, ReadError, ReadTimeout

from crypto_trailing_stop.commons.constants import IDEMPOTENT_HTTP_METHODS

logger = logging.getLogger(__name__)


def backoff_on_backoff_handler(details: dict[str, Any]) -> None:
    logger.warning(
        f"[Retry {details['tries']}] " + f"Waiting {details['wait']:.2f}s due to {str(details['exception'])}"
    )


def prepare_backoff_giveup_handler_fn(retryable_http_status_codes: list[int] | int = []) -> Callable[[Exception], bool]:
    retryable_http_status_codes = retryable_http_status_codes or []
    retryable_http_status_codes = (
        retryable_http_status_codes
        if isinstance(retryable_http_status_codes, (list, set, tuple, frozenset))
        else [retryable_http_status_codes]
    )

    def __backoff_giveup_handler(e: Exception) -> bool:
        should_give_up = False
        if isinstance(e, (ReadTimeout, ReadError)):
            method = getattr(e.request, "method", "GET").upper()
            should_give_up = method != "GET"
        elif isinstance(e, ValueError):
            cause = e.__cause__
            if not isinstance(cause, HTTPStatusError):
                should_give_up = True
            else:
                method = getattr(getattr(cause, "request", None), "method", "GET").upper()
                status_code = getattr(getattr(cause, "response", None), "status_code", None)
                if method not in IDEMPOTENT_HTTP_METHODS:
                    should_give_up = status_code not in retryable_http_status_codes
                else:
                    should_give_up = status_code not in (*retryable_http_status_codes, 500)
        return should_give_up

    return __backoff_giveup_handler
