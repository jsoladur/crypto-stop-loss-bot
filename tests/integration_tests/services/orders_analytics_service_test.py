import json
import logging
from os import listdir, path
from unittest.mock import patch
from urllib.parse import urlencode

import ccxt.async_support as ccxt
import pytest
from faker import Faker
from pydantic import RootModel
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType
from werkzeug import Response

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_pagination_result_dto import Bit2MePaginationResultDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_trade_dto import Bit2MeTradeDto
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.orders_analytics_service import OrdersAnalyticsService
from crypto_trailing_stop.infrastructure.services.stop_loss_percent_service import StopLossPercentService
from tests.helpers.constants import BUY_SELL_SIGNALS_MOCK_FILES_PATH
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMacher
from tests.helpers.object_mothers import Bit2MeOrderDtoObjectMother
from tests.helpers.sell_orders_test_utils import generate_trades

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def should_calculate_all_limit_sell_order_guard_metrics_properly(
    faker: Faker, integration_test_jobs_disabled_env: tuple[HTTPServer, str]
) -> None:
    _, httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_jobs_disabled_env
    bit2me_remote_service = Bit2MeRemoteService()
    orders_analytics_service = OrdersAnalyticsService(
        bit2me_remote_service=bit2me_remote_service,
        stop_loss_percent_service=StopLossPercentService(global_flag_service=GlobalFlagService()),
        crypto_analytics_service=CryptoAnalyticsService(
            bit2me_remote_service=bit2me_remote_service, ccxt_remote_service=CcxtRemoteService()
        ),
    )

    opened_sell_bit2me_orders, *_ = _prepare_httpserver_mock(faker, httpserver, bit2me_api_key, bit2me_api_secret)
    first_sell_order, *_ = opened_sell_bit2me_orders

    fetch_ohlcv_return_value_filename = faker.random_element(
        [filename for filename in listdir(BUY_SELL_SIGNALS_MOCK_FILES_PATH) if filename.endswith(".json")]
    )
    with open(path.join(BUY_SELL_SIGNALS_MOCK_FILES_PATH, fetch_ohlcv_return_value_filename)) as fd:
        fetch_ohlcv_return_value = json.loads(fd.read())
        with patch.object(ccxt.binance, "fetch_ohlcv", return_value=fetch_ohlcv_return_value):
            limit_sell_order_guard_metrics = (
                await orders_analytics_service.calculate_all_limit_sell_order_guard_metrics(
                    symbol=first_sell_order.symbol
                )
            )
            for idx, sell_order in enumerate(opened_sell_bit2me_orders):
                logger.info(repr(limit_sell_order_guard_metrics))
                metrics = limit_sell_order_guard_metrics[idx]
                assert metrics.sell_order.id == sell_order.id
                assert metrics.sell_order.status == sell_order.status
                assert metrics.sell_order.order_amount == sell_order.order_amount
                assert metrics.sell_order.stop_price == sell_order.stop_price
                assert metrics.sell_order.price == sell_order.price
                assert metrics.sell_order.side == sell_order.side
                assert metrics.sell_order.symbol == sell_order.symbol
                assert metrics.sell_order.order_type == sell_order.order_type

                assert metrics.avg_buy_price is not None and metrics.avg_buy_price > 0
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
    faker: Faker, httpserver: HTTPServer, bit2me_api_key: str, bik2me_api_secret: str
) -> tuple[list[Bit2MeOrderDto]]:
    symbol = faker.random_element(["ETH/EUR", "SOL/EUR"])
    opened_sell_bit2me_orders = [
        Bit2MeOrderDtoObjectMother.create(
            side="sell", order_type="stop-limit", symbol=symbol, status=faker.random_element(["open", "inactive"])
        ),
        Bit2MeOrderDtoObjectMother.create(
            side="sell", order_type="limit", symbol=symbol, status=faker.random_element(["open", "inactive"])
        ),
    ]
    buy_trades = generate_trades(faker, opened_sell_bit2me_orders)
    # Mock call to /v1/trading/order to get opened sell orders
    httpserver.expect(
        Bit2MeAPIRequestMacher(
            "/bit2me-api/v1/trading/order",
            method="GET",
            query_string=urlencode({"direction": "desc", "status_in": "open,inactive", "side": "sell"}, doseq=False),
        ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_json(
        RootModel[list[Bit2MeOrderDto]](opened_sell_bit2me_orders).model_dump(mode="json", by_alias=True)
    )

    for sell_order in opened_sell_bit2me_orders:
        # Mock call to /v1/trading/trade to get closed buy trades
        httpserver.expect(
            Bit2MeAPIRequestMacher(
                "/bit2me-api/v1/trading/trade",
                method="GET",
                query_string=urlencode({"direction": "desc", "side": "buy", "symbol": sell_order.symbol}, doseq=False),
            ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
            handler_type=HandlerType.ONESHOT,
        ).respond_with_response(Response(status=403))
        # Mock trades /v1/trading/trade
        httpserver.expect(
            Bit2MeAPIRequestMacher(
                "/bit2me-api/v1/trading/trade",
                method="GET",
                query_string=urlencode({"direction": "desc", "side": "buy", "symbol": sell_order.symbol}, doseq=False),
            ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
            handler_type=HandlerType.ONESHOT,
        ).respond_with_json(
            Bit2MePaginationResultDto[Bit2MeTradeDto](
                data=buy_trades, total=faker.pyint(min_value=len(buy_trades), max_value=len(buy_trades) * 10)
            ).model_dump(mode="json", by_alias=True)
        )
    return (opened_sell_bit2me_orders,)
