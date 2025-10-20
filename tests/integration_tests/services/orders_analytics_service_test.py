import logging
from urllib.parse import urlencode

import pytest
from faker import Faker
from pydantic import RootModel
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType
from werkzeug import Response

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_pagination_result_dto import Bit2MePaginationResultDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_trade_dto import Bit2MeTradeDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_order_dto import MEXCOrderDto, MEXCOrderStatus
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_trade_dto import MEXCTradeDto
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import (
    OperatingExchangeEnum,
    OrderStatusEnum,
)
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.orders_analytics_service import OrdersAnalyticsService
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMatcher, CustomAPIQueryMatcher, MEXCAPIRequestMatcher
from tests.helpers.httpserver_pytest.utils import (
    prepare_httpserver_fetch_ohlcv_mock,
    prepare_httpserver_tickers_list_mock,
)
from tests.helpers.object_mothers import Bit2MeOrderDtoObjectMother, MEXCOrderDtoObjectMother
from tests.helpers.sell_orders_test_utils import generate_bit2me_trades, generate_mexc_trades

logger = logging.getLogger(__name__)


@pytest.mark.parametrize("previous_stored_buy_sell_signals_config", [True, False])
@pytest.mark.asyncio
async def should_calculate_all_limit_sell_order_guard_metrics_properly(
    faker: Faker,
    previous_stored_buy_sell_signals_config: bool,
    integration_test_jobs_disabled_env: tuple[HTTPServer, str],
) -> None:
    _, httpserver, api_key, api_secret, operating_exchange, *_ = integration_test_jobs_disabled_env
    buy_sell_signals_config_service: BuySellSignalsConfigService = (
        get_application_container().infrastructure_container().services_container().buy_sell_signals_config_service()
    )
    orders_analytics_service: OrdersAnalyticsService = (
        get_application_container().infrastructure_container().services_container().orders_analytics_service()
    )
    opened_sell_orders, symbol = _prepare_httpserver_mock(faker, httpserver, operating_exchange, api_key, api_secret)

    if previous_stored_buy_sell_signals_config:
        expected_buy_sell_signals_config_item = BuySellSignalsConfigItem(
            symbol=symbol.split("/")[0],
            ema_short_value=faker.pyint(min_value=5, max_value=9),
            ema_mid_value=faker.pyint(min_value=18, max_value=30),
            ema_long_value=faker.pyint(min_value=200, max_value=250),
            enable_exit_on_sell_signal=faker.pybool(),
            enable_exit_on_take_profit=faker.pybool(),
            stop_loss_atr_multiplier=faker.pyfloat(min_value=2.5, max_value=6.5),
            take_profit_atr_multiplier=faker.pyfloat(min_value=2.5, max_value=6.5),
            adx_threshold=faker.pyint(min_value=20, max_value=40),
            buy_min_volume_threshold=faker.pyfloat(min_value=0.5, max_value=2.5),
            buy_max_volume_threshold=faker.pyfloat(min_value=3.0, max_value=10.0),
            sell_min_volume_threshold=faker.pyfloat(min_value=0.5, max_value=2.5),
        )
        await buy_sell_signals_config_service.save_or_update(expected_buy_sell_signals_config_item)

    limit_sell_order_guard_metrics = await orders_analytics_service.calculate_all_limit_sell_order_guard_metrics(
        symbol=symbol
    )
    for idx, sell_order in enumerate(opened_sell_orders):
        logger.info(repr(limit_sell_order_guard_metrics))
        metrics = limit_sell_order_guard_metrics[idx]
        if isinstance(sell_order, Bit2MeOrderDto):
            assert metrics.sell_order.id == sell_order.id
            assert metrics.sell_order.amount == sell_order.order_amount
            assert metrics.sell_order.order_type == sell_order.order_type
            assert metrics.sell_order.status == sell_order.status
            assert metrics.sell_order.price == sell_order.price
            assert metrics.sell_order.stop_price == sell_order.stop_price
        else:
            assert metrics.sell_order.id == str(sell_order.order_id)
            assert metrics.sell_order.amount == float(sell_order.qty)
            assert metrics.sell_order.amount == float(sell_order.executed_qty)
            assert metrics.sell_order.order_type.name.upper() == sell_order.type.upper()
            assert metrics.sell_order.status == _map_mexc_status(sell_order.status)
            assert metrics.sell_order.price == float(sell_order.price)
            assert (
                metrics.sell_order.stop_price is None
                and sell_order.stop_price is None
                or metrics.sell_order.stop_price == float(sell_order.stop_price)
            )

        assert metrics.sell_order.side.value.lower() == sell_order.side.lower()
        assert metrics.sell_order.symbol == symbol

        assert metrics.avg_buy_price is not None and metrics.avg_buy_price > 0
        assert metrics.current_price is not None and metrics.current_price > 0
        assert metrics.current_profit is not None
        assert metrics.net_revenue is not None
        assert metrics.break_even_price is not None and metrics.break_even_price > metrics.avg_buy_price
        assert metrics.safeguard_stop_price > 0 and metrics.safeguard_stop_price < metrics.avg_buy_price
        assert metrics.stop_loss_percent_value > 0
        assert metrics.current_attr_value > 0.0
        assert (
            metrics.suggested_safeguard_stop_price > 0
            and metrics.suggested_safeguard_stop_price < metrics.avg_buy_price
        )
        assert (
            metrics.suggested_take_profit_limit_price > 0
            and metrics.suggested_take_profit_limit_price > metrics.avg_buy_price
        )

    httpserver.check_assertions()


def _prepare_httpserver_mock(
    faker: Faker, httpserver: HTTPServer, operating_exchange: OperatingExchangeEnum, api_key: str, api_secret: str
) -> tuple[list[Bit2MeOrderDto] | list[MEXCOrderDto]]:
    *_, symbol = prepare_httpserver_tickers_list_mock(faker, httpserver, operating_exchange, api_key, api_secret)
    prepare_httpserver_fetch_ohlcv_mock(faker, httpserver, operating_exchange, api_key, api_secret, symbol)
    opened_sell_orders = _prepare_httpserver_open_sell_orders_mock(
        faker, httpserver, operating_exchange, api_key, api_secret, symbol
    )
    _prepare_httpserver_trades_mock(faker, httpserver, operating_exchange, api_key, api_secret, opened_sell_orders)
    return (opened_sell_orders, symbol)


def _prepare_httpserver_open_sell_orders_mock(
    faker: Faker,
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    symbol: str,
) -> list[Bit2MeOrderDto] | list[MEXCOrderDto]:
    match operating_exchange:
        case OperatingExchangeEnum.BIT2ME:
            opened_sell_orders = [
                Bit2MeOrderDtoObjectMother.create(
                    side="sell",
                    order_type="stop-limit",
                    symbol=symbol,
                    status=faker.random_element(["open", "inactive"]),
                ),
                Bit2MeOrderDtoObjectMother.create(
                    side="sell", order_type="limit", symbol=symbol, status=faker.random_element(["open", "inactive"])
                ),
            ]
            # Mock call to /v1/trading/order to get opened sell orders
            httpserver.expect(
                Bit2MeAPIRequestMatcher(
                    "/bit2me-api/v1/trading/order",
                    method="GET",
                    query_string=urlencode(
                        {"direction": "desc", "status_in": "open,inactive", "side": "sell"}, doseq=False
                    ),
                ).set_api_key_and_secret(api_key, api_secret),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_json(
                RootModel[list[Bit2MeOrderDto]](opened_sell_orders).model_dump(mode="json", by_alias=True)
            )
        case OperatingExchangeEnum.MEXC:
            opened_sell_orders = [
                MEXCOrderDtoObjectMother.create(side="SELL", symbol=symbol, order_type="STOP_LIMIT", status="NEW"),
                MEXCOrderDtoObjectMother.create(side="SELL", symbol=symbol, order_type="LIMIT", status="NEW"),
            ]
            httpserver.expect(
                MEXCAPIRequestMatcher("/mexc-api/api/v3/openOrders", method="GET").set_api_key_and_secret(
                    api_key, api_secret
                ),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_json(
                RootModel[list[MEXCOrderDto]](opened_sell_orders).model_dump(mode="json", by_alias=True)
            )

    return opened_sell_orders


def _prepare_httpserver_trades_mock(
    faker: Faker,
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    opened_sell_orders: list[Bit2MeOrderDto] | list[MEXCOrderDto],
) -> None:
    match operating_exchange:
        case OperatingExchangeEnum.BIT2ME:
            buy_trades, *_ = generate_bit2me_trades(faker, opened_sell_orders)
            for sell_order in opened_sell_orders:
                # Mock call to /v1/trading/trade to get closed buy trades
                httpserver.expect(
                    Bit2MeAPIRequestMatcher(
                        "/bit2me-api/v1/trading/trade",
                        method="GET",
                        query_string=urlencode(
                            {"direction": "desc", "side": "buy", "symbol": sell_order.symbol}, doseq=False
                        ),
                    ).set_api_key_and_secret(api_key, api_secret),
                    handler_type=HandlerType.ONESHOT,
                ).respond_with_response(Response(status=403))
                # Mock trades /v1/trading/trade
                httpserver.expect(
                    Bit2MeAPIRequestMatcher(
                        "/bit2me-api/v1/trading/trade",
                        method="GET",
                        query_string=urlencode(
                            {"direction": "desc", "side": "buy", "symbol": sell_order.symbol}, doseq=False
                        ),
                    ).set_api_key_and_secret(api_key, api_secret),
                    handler_type=HandlerType.ONESHOT,
                ).respond_with_json(
                    Bit2MePaginationResultDto[Bit2MeTradeDto](
                        data=buy_trades, total=faker.pyint(min_value=len(buy_trades), max_value=len(buy_trades) * 10)
                    ).model_dump(mode="json", by_alias=True)
                )
        case OperatingExchangeEnum.MEXC:
            buy_trades, *_ = generate_mexc_trades(faker, opened_sell_orders)
            for sell_order in opened_sell_orders:
                httpserver.expect(
                    MEXCAPIRequestMatcher(
                        "/mexc-api/api/v3/myTrades",
                        method="GET",
                        query_string=CustomAPIQueryMatcher(
                            {"symbol": sell_order.symbol}, additional_required_query_params=["signature", "timestamp"]
                        ),
                    ).set_api_key_and_secret(api_key, api_secret),
                    handler_type=HandlerType.ONESHOT,
                ).respond_with_json(RootModel[list[MEXCTradeDto]](buy_trades).model_dump(mode="json", by_alias=True))
        case _:
            raise ValueError(f"Unsupported operating exchange: {operating_exchange}")


def _map_mexc_status(mexc_status: MEXCOrderStatus) -> OrderStatusEnum:
    match mexc_status:
        case "NEW":
            ret = OrderStatusEnum.OPEN
        case "FILLED":
            ret = OrderStatusEnum.FILLED
        case "PARTIALLY_FILLED":
            ret = OrderStatusEnum.PARTIALLY_FILLED
        case "CANCELED":
            ret = OrderStatusEnum.CANCELLED
        case "PARTIALLY_CANCELED":
            ret = OrderStatusEnum.PARTIALLY_CANCELLED
        case _:
            raise ValueError(f"Unknown MEXC order status: {mexc_status}")
    return ret
