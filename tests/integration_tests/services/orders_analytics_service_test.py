import logging
from urllib.parse import urlencode

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
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.orders_analytics_service import OrdersAnalyticsService
from crypto_trailing_stop.infrastructure.services.stop_loss_percent_service import StopLossPercentService
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from tests.helpers.constants import MOCK_CRYPTO_CURRENCIES
from tests.helpers.httpserver_pytest import Bit2MeAPIQueryMatcher, Bit2MeAPIRequestMacher
from tests.helpers.object_mothers import Bit2MeOrderDtoObjectMother
from tests.helpers.ohlcv_test_utils import get_fetch_ohlcv_random_result
from tests.helpers.sell_orders_test_utils import generate_trades

logger = logging.getLogger(__name__)


@pytest.mark.parametrize("previous_stored_buy_sell_signals_config", [True, False])
@pytest.mark.asyncio
async def should_calculate_all_limit_sell_order_guard_metrics_properly(
    faker: Faker,
    previous_stored_buy_sell_signals_config: bool,
    integration_test_jobs_disabled_env: tuple[HTTPServer, str],
) -> None:
    _, httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_jobs_disabled_env
    bit2me_remote_service = Bit2MeRemoteService()
    ccxt_remote_service = CcxtRemoteService()
    buy_sell_signals_config_service = BuySellSignalsConfigService(bit2me_remote_service=bit2me_remote_service)
    orders_analytics_service = OrdersAnalyticsService(
        bit2me_remote_service=bit2me_remote_service,
        ccxt_remote_service=ccxt_remote_service,
        stop_loss_percent_service=StopLossPercentService(global_flag_service=GlobalFlagService()),
        buy_sell_signals_config_service=buy_sell_signals_config_service,
        crypto_analytics_service=CryptoAnalyticsService(
            bit2me_remote_service=bit2me_remote_service,
            ccxt_remote_service=ccxt_remote_service,
            buy_sell_signals_config_service=buy_sell_signals_config_service,
        ),
    )
    opened_sell_bit2me_orders, *_ = _prepare_httpserver_mock(faker, httpserver, bit2me_api_key, bit2me_api_secret)
    first_sell_order, *_ = opened_sell_bit2me_orders

    if previous_stored_buy_sell_signals_config:
        expected_buy_sell_signals_config_item = BuySellSignalsConfigItem(
            symbol=first_sell_order.symbol.split("/")[0],
            ema_short_value=faker.pyint(min_value=5, max_value=9),
            ema_mid_value=faker.pyint(min_value=18, max_value=30),
            ema_long_value=faker.pyint(min_value=200, max_value=250),
            auto_exit_sell_1h=faker.pybool(),
            auto_exit_atr_take_profit=faker.pybool(),
            stop_loss_atr_multiplier=faker.pyfloat(min_value=2.5, max_value=6.5),
            take_profit_atr_multiplier=faker.pyfloat(min_value=2.5, max_value=6.5),
        )
        await buy_sell_signals_config_service.save_or_update(expected_buy_sell_signals_config_item)

    limit_sell_order_guard_metrics = await orders_analytics_service.calculate_all_limit_sell_order_guard_metrics(
        symbol=first_sell_order.symbol
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
    symbol = f"{faker.random_element(MOCK_CRYPTO_CURRENCIES)}/EUR"
    # Mock OHLCV /v1/trading/candle
    fetch_ohlcv_return_value = get_fetch_ohlcv_random_result(faker)
    httpserver.expect(
        Bit2MeAPIRequestMacher(
            "/bit2me-api/v1/trading/candle",
            method="GET",
            query_string=Bit2MeAPIQueryMatcher(
                {"symbol": symbol, "interval": 60, "limit": 251},
                additional_required_query_params=["startTime", "endTime"],
            ),
        ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_json(fetch_ohlcv_return_value)

    opened_sell_bit2me_orders = [
        Bit2MeOrderDtoObjectMother.create(
            side="sell", order_type="stop-limit", symbol=symbol, status=faker.random_element(["open", "inactive"])
        ),
        Bit2MeOrderDtoObjectMother.create(
            side="sell", order_type="limit", symbol=symbol, status=faker.random_element(["open", "inactive"])
        ),
    ]
    buy_trades, *_ = generate_trades(faker, opened_sell_bit2me_orders)
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
