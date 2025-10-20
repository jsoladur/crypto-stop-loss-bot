from typing import Any

from faker import Faker
from pydantic import RootModel
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_ticker_book_dto import MEXCTickerBookDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_ticker_price_dto import MEXCTickerPriceDto
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import OperatingExchangeEnum
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMatcher, CustomAPIQueryMatcher, MEXCAPIRequestMatcher
from tests.helpers.market_config_utils import load_mexc_exchange_symbol_config_by_mexc_symbol
from tests.helpers.object_mothers import Bit2MeTickersDtoObjectMother, MEXCTickerPriceAndBookDtoObjectMother
from tests.helpers.ohlcv_test_utils import get_fetch_ohlcv_random_result


def prepare_httpserver_fetch_ohlcv_mock(
    faker: Faker,
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    symbol: str,
    *,
    fetch_ohlcv_return_value: list[list[Any]] | None = None,
) -> None:
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
            # FIXME: This MOCK is not being effective. We have to see how to mock it!
            httpserver.expect_request(
                "/mexc-api/api/v3/klines", method="GET", query_string={"symbol": symbol, "interval": 60, "limit": 251}
            ).respond_with_json(fetch_ohlcv_return_value)
        case _:
            raise ValueError(f"Unknown operating exchange: {operating_exchange}")


def prepare_httpserver_tickers_list_mock(
    faker: Faker,
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    *,
    tickers_list: list[Bit2MeTickersDto] | list[tuple[MEXCTickerPriceDto, MEXCTickerBookDto]] = None,
    handler_type: HandlerType = HandlerType.ONESHOT,
) -> tuple[list[Bit2MeTickersDto] | list[tuple[MEXCTickerPriceDto, MEXCTickerBookDto]], str]:
    match operating_exchange:
        case OperatingExchangeEnum.BIT2ME:
            tickers_list = tickers_list or Bit2MeTickersDtoObjectMother.list()
            symbol = faker.random_element([ticker.symbol for ticker in tickers_list])
            httpserver.expect(
                Bit2MeAPIRequestMatcher("/bit2me-api/v2/trading/tickers", method="GET").set_api_key_and_secret(
                    api_key, api_secret
                ),
                handler_type=handler_type,
            ).respond_with_json(RootModel[list[Bit2MeTickersDto]](tickers_list).model_dump(mode="json", by_alias=True))
        case OperatingExchangeEnum.MEXC:
            tickers_list = tickers_list or MEXCTickerPriceAndBookDtoObjectMother.list()
            mexc_symbol = faker.random_element([price.symbol for price, _ in tickers_list])
            mexc_exchange_symbol_config = load_mexc_exchange_symbol_config_by_mexc_symbol(mexc_symbol)
            symbol = f"{mexc_exchange_symbol_config.base_asset}/{mexc_exchange_symbol_config.quote_asset}"
            httpserver.expect(
                MEXCAPIRequestMatcher("/mexc-api/api/v3/ticker/price", method="GET").set_api_key_and_secret(
                    api_key, api_secret
                )
            ).respond_with_json(
                RootModel[list[MEXCTickerPriceDto]]([price for price, _ in tickers_list]).model_dump(
                    mode="json", by_alias=True
                )
            )
            httpserver.expect(
                MEXCAPIRequestMatcher("/mexc-api/api/v3/ticker/bookTicker", method="GET").set_api_key_and_secret(
                    api_key, api_secret
                )
            ).respond_with_json(
                RootModel[list[MEXCTickerBookDto]]([book for _, book in tickers_list]).model_dump(
                    mode="json", by_alias=True
                )
            )
        case _:
            raise ValueError(f"Unsupported operating exchange: {operating_exchange}")
    return tickers_list, symbol
