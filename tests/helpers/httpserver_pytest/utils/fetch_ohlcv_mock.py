import logging
from typing import Any

from faker import Faker
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType

from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import OperatingExchangeEnum
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMatcher, CustomAPIQueryMatcher
from tests.helpers.ohlcv_test_utils import get_fetch_ohlcv_random_result

logger = logging.getLogger(__name__)


def prepare_httpserver_fetch_ohlcv_mock(
    faker: Faker,
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    symbol: str,
    *,
    fetch_ohlcv_return_value: list[list[Any]] | None = None,
) -> list[list[Any]]:
    # Mock OHLCV /v1/trading/candle
    fetch_ohlcv_return_value = fetch_ohlcv_return_value or get_fetch_ohlcv_random_result(faker)
    match operating_exchange:
        case OperatingExchangeEnum.BIT2ME:
            httpserver.expect(
                Bit2MeAPIRequestMatcher(
                    "/bit2me-api/v1/trading/candle",
                    method="GET",
                    query_string=CustomAPIQueryMatcher(
                        {"symbol": symbol, "interval": 60, "limit": 251},
                        additional_required_query_params=["startTime", "endTime"],
                    ),
                ).set_api_key_and_secret(api_key, api_secret),
                handler_type=HandlerType.PERMANENT,
            ).respond_with_json(fetch_ohlcv_return_value)
        case OperatingExchangeEnum.MEXC:
            logger.debug("MEXC mock will be setup via unittest.mock.patch(..)...")
        case _:
            raise ValueError(f"Unknown operating exchange: {operating_exchange}")
    return fetch_ohlcv_return_value
