from urllib.parse import urlencode

from faker import Faker
from pydantic import RootModel
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType
from werkzeug import Response

from crypto_trailing_stop.commons.constants import BIT2ME_RETRYABLE_HTTP_STATUS_CODES
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_pagination_result_dto import Bit2MePaginationResultDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_trade_dto import Bit2MeTradeDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_order_dto import MEXCOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_trade_dto import MEXCTradeDto
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import OperatingExchangeEnum
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMatcher, CustomAPIQueryMatcher, MEXCAPIRequestMatcher
from tests.helpers.sell_orders_test_utils import generate_bit2me_trades, generate_mexc_trades


def prepare_httpserver_trades_mock(
    faker: Faker,
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    opened_sell_orders: list[Bit2MeOrderDto] | list[MEXCOrderDto],
    *,
    buy_trades: list[Bit2MeTradeDto] | list[MEXCTradeDto] | None = None,
    number_of_trades: int | None = None,
    operating_exchange_error_status_code: int | None = None,
    handler_type: HandlerType = HandlerType.ONESHOT,
) -> (
    tuple[list[Bit2MeTradeDto], list[tuple[Bit2MeOrderDto, float]]]
    | tuple[list[MEXCTradeDto], list[tuple[MEXCOrderDto, float]]]
):
    buy_prices = []
    match operating_exchange:
        case OperatingExchangeEnum.BIT2ME:
            if not buy_trades:
                buy_trades, buy_prices = generate_bit2me_trades(
                    faker, opened_sell_orders, number_of_trades=number_of_trades
                )
            for sell_order in opened_sell_orders:
                if (
                    operating_exchange_error_status_code is not None
                    and operating_exchange_error_status_code in BIT2ME_RETRYABLE_HTTP_STATUS_CODES
                ):
                    # Mock call to /v1/trading/trade to get closed buy trades
                    httpserver.expect(
                        Bit2MeAPIRequestMatcher(
                            "/bit2me-api/v1/trading/trade",
                            method="GET",
                            query_string=urlencode(
                                {"direction": "desc", "side": "buy", "symbol": sell_order.symbol}, doseq=False
                            ),
                        ).set_api_key_and_secret(api_key, api_secret),
                        handler_type=handler_type,
                    ).respond_with_response(Response(status=operating_exchange_error_status_code))
                # Mock trades /v1/trading/trade
                httpserver.expect(
                    Bit2MeAPIRequestMatcher(
                        "/bit2me-api/v1/trading/trade",
                        method="GET",
                        query_string=urlencode(
                            {"direction": "desc", "side": "buy", "symbol": sell_order.symbol}, doseq=False
                        ),
                    ).set_api_key_and_secret(api_key, api_secret),
                    handler_type=handler_type,
                ).respond_with_json(
                    Bit2MePaginationResultDto[Bit2MeTradeDto](
                        data=buy_trades, total=faker.pyint(min_value=len(buy_trades), max_value=len(buy_trades) * 10)
                    ).model_dump(mode="json", by_alias=True)
                )
        case OperatingExchangeEnum.MEXC:
            if not buy_trades:
                buy_trades, buy_prices = generate_mexc_trades(
                    faker, opened_sell_orders, number_of_trades=number_of_trades
                )
            for sell_order in opened_sell_orders:
                httpserver.expect(
                    MEXCAPIRequestMatcher(
                        "/mexc-api/api/v3/myTrades",
                        method="GET",
                        query_string=CustomAPIQueryMatcher(
                            {"symbol": sell_order.symbol}, additional_required_query_params=["signature", "timestamp"]
                        ),
                    ).set_api_key_and_secret(api_key, api_secret),
                    handler_type=handler_type,
                ).respond_with_json(RootModel[list[MEXCTradeDto]](buy_trades).model_dump(mode="json", by_alias=True))
        case _:
            raise ValueError(f"Unsupported operating exchange: {operating_exchange}")
    return buy_trades, buy_prices
