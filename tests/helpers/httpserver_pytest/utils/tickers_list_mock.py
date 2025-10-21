import logging

from faker import Faker
from pydantic import RootModel
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_ticker_book_dto import MEXCTickerBookDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_ticker_price_dto import MEXCTickerPriceDto
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import OperatingExchangeEnum
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMatcher, MEXCAPIRequestMatcher
from tests.helpers.market_config_test_utils import load_mexc_exchange_symbol_config_dict
from tests.helpers.object_mothers import Bit2MeTickersDtoObjectMother, MEXCTickerPriceAndBookDtoObjectMother

logger = logging.getLogger(__name__)


def prepare_httpserver_tickers_list_mock(
    faker: Faker,
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    *,
    tickers_list: list[Bit2MeTickersDto] | list[tuple[MEXCTickerPriceDto, MEXCTickerBookDto]] = None,
    handler_type: HandlerType = HandlerType.ONESHOT,
) -> tuple[list[Bit2MeTickersDto] | list[tuple[MEXCTickerPriceDto, MEXCTickerBookDto]], list[str], str]:
    match operating_exchange:
        case OperatingExchangeEnum.BIT2ME:
            tickers_list = tickers_list or Bit2MeTickersDtoObjectMother.list()
            all_symbols = [ticker.symbol for ticker in tickers_list]
            symbol = faker.random_element([ticker.symbol for ticker in tickers_list])
            httpserver.expect(
                Bit2MeAPIRequestMatcher("/bit2me-api/v2/trading/tickers", method="GET").set_api_key_and_secret(
                    api_key, api_secret
                ),
                handler_type=handler_type,
            ).respond_with_json(RootModel[list[Bit2MeTickersDto]](tickers_list).model_dump(mode="json", by_alias=True))
        case OperatingExchangeEnum.MEXC:
            tickers_list = tickers_list or MEXCTickerPriceAndBookDtoObjectMother.list()
            mexc_exchange_symbol_config_dict = load_mexc_exchange_symbol_config_dict()
            all_symbols = [
                f"{mexc_exchange_symbol_config_dict[price.symbol].base_asset}/{mexc_exchange_symbol_config_dict[price.symbol].quote_asset}"
                for price, _ in tickers_list
            ]
            symbol = faker.random_element(all_symbols)
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
    return tickers_list, all_symbols, symbol
