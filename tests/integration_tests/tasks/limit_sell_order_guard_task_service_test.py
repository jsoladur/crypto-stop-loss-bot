import asyncio
import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from aiogram import Bot
from faker import Faker
from pydantic import RootModel
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType
from werkzeug import Response

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_pagination_result_dto import Bit2MePaginationResultDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_trade_dto import Bit2MeTradeDto
from crypto_trailing_stop.infrastructure.database.models.push_notification import PushNotification
from crypto_trailing_stop.infrastructure.services.enums.global_flag_enum import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.enums.push_notification_type_enum import PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.market_signal_service import MarketSignalService
from crypto_trailing_stop.infrastructure.tasks import get_task_manager_instance
from crypto_trailing_stop.infrastructure.tasks.limit_sell_order_guard_task_service import LimitSellOrderGuardTaskService
from tests.helpers.background_jobs_test_utils import disable_all_background_jobs_except
from tests.helpers.httpserver_pytest import Bit2MeAPIQueryMatcher, Bit2MeAPIRequestMacher
from tests.helpers.object_mothers import (
    Bit2MeOrderDtoObjectMother,
    Bit2MeTickersDtoObjectMother,
    SignalsEvaluationResultObjectMother,
)
from tests.helpers.ohlcv_test_utils import get_fetch_ohlcv_random_result
from tests.helpers.sell_orders_test_utils import generate_trades

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def should_create_market_sell_order_when_atr_take_profit_limit_price_reached(
    faker: Faker, integration_test_env: tuple[HTTPServer, str]
) -> None:
    """
    Test that all expected calls to Bit2Me are made when a limit sell order has to be filled
    """
    # Mock the Bit2Me API
    _, httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_env
    # Disable all jobs by default for test purposes!
    await disable_all_background_jobs_except(exclusion=GlobalFlagTypeEnum.AUTO_EXIT_ATR_TAKE_PROFIT)

    opened_sell_bit2me_orders = _prepare_httpserver_mock(
        faker, httpserver, bit2me_api_key, bit2me_api_secret, closing_crypto_currency_price_multipler=1.5
    )

    task_manager = get_task_manager_instance()
    first_order, *_ = opened_sell_bit2me_orders

    # Create fake market signals to simulate the sudden SELL 1H market signal
    await _create_fake_market_signals(first_order)

    # Provoke send a notification via Telegram
    telegram_chat_id = faker.random_number(digits=9, fix_len=True)
    for push_notification_type in PushNotificationTypeEnum:
        push_notification = PushNotification(
            {
                PushNotification.telegram_chat_id: telegram_chat_id,
                PushNotification.notification_type: push_notification_type,
            }
        )
        await push_notification.save()

    limit_sell_order_guard_task_service: LimitSellOrderGuardTaskService = task_manager.get_tasks()[
        GlobalFlagTypeEnum.LIMIT_SELL_ORDER_GUARD
    ]
    with patch.object(
        LimitSellOrderGuardTaskService, "_notify_fatal_error_via_telegram"
    ) as notify_fatal_error_via_telegram_mock:
        with patch.object(Bot, "send_message"):
            await limit_sell_order_guard_task_service.run()

            notify_fatal_error_via_telegram_mock.assert_not_called()
            httpserver.check_assertions()


@pytest.mark.parametrize("simulate_future_sell_orders", [False, True])
@pytest.mark.asyncio
async def should_create_market_sell_order_when_auto_exit_sell_1h(
    faker: Faker, simulate_future_sell_orders: bool, integration_test_env: tuple[HTTPServer, str]
) -> None:
    """
    Test that all expected calls to Bit2Me are made when a limit sell order has to be filled
    """
    # Mock the Bit2Me API
    _, httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_env
    # Disable all jobs by default for test purposes!
    await disable_all_background_jobs_except(exclusion=GlobalFlagTypeEnum.AUTO_EXIT_SELL_1H)

    opened_sell_bit2me_orders = _prepare_httpserver_mock(
        faker,
        httpserver,
        bit2me_api_key,
        bit2me_api_secret,
        closing_crypto_currency_price_multipler=1.5,
        simulate_future_sell_orders=simulate_future_sell_orders,
    )
    first_order, *_ = opened_sell_bit2me_orders

    task_manager = get_task_manager_instance()

    # Create fake market signals to simulate the sudden SELL 1H market signal
    await _create_fake_market_signals(first_order)

    # Provoke send a notification via Telegram
    telegram_chat_id = faker.random_number(digits=9, fix_len=True)
    for push_notification_type in PushNotificationTypeEnum:
        push_notification = PushNotification(
            {
                PushNotification.telegram_chat_id: telegram_chat_id,
                PushNotification.notification_type: push_notification_type,
            }
        )
        await push_notification.save()

    limit_sell_order_guard_task_service: LimitSellOrderGuardTaskService = task_manager.get_tasks()[
        GlobalFlagTypeEnum.LIMIT_SELL_ORDER_GUARD
    ]
    with patch.object(
        LimitSellOrderGuardTaskService, "_notify_fatal_error_via_telegram"
    ) as notify_fatal_error_via_telegram_mock:
        with patch.object(Bot, "send_message"):
            await limit_sell_order_guard_task_service.run()
            notify_fatal_error_via_telegram_mock.assert_not_called()
            httpserver.check_assertions()


@pytest.mark.parametrize("bit2me_error_status_code", [403, 500, 502])
@pytest.mark.asyncio
async def should_create_market_sell_order_when_safeguard_stop_price_reached(
    faker: Faker, bit2me_error_status_code: int, integration_test_env: tuple[HTTPServer, str]
) -> None:
    """
    Test that all expected calls to Bit2Me are made when a limit sell order has to be filled
    """
    # Mock the Bit2Me API
    _, httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_env
    # Disable all jobs by default for test purposes!
    await disable_all_background_jobs_except(exclusion=GlobalFlagTypeEnum.AUTO_EXIT_SELL_1H)

    _prepare_httpserver_mock(
        faker,
        httpserver,
        bit2me_api_key,
        bit2me_api_secret,
        bit2me_error_status_code=bit2me_error_status_code,
        closing_crypto_currency_price_multipler=0.2,
    )

    task_manager = get_task_manager_instance()

    # Provoke send a notification via Telegram
    telegram_chat_id = faker.random_number(digits=9, fix_len=True)
    for push_notification_type in PushNotificationTypeEnum:
        push_notification = PushNotification(
            {
                PushNotification.telegram_chat_id: telegram_chat_id,
                PushNotification.notification_type: push_notification_type,
            }
        )
        await push_notification.save()

    limit_sell_order_guard_task_service: LimitSellOrderGuardTaskService = task_manager.get_tasks()[
        GlobalFlagTypeEnum.LIMIT_SELL_ORDER_GUARD
    ]
    with patch.object(
        LimitSellOrderGuardTaskService, "_notify_fatal_error_via_telegram"
    ) as notify_fatal_error_via_telegram_mock:
        with patch.object(Bot, "send_message"):
            await limit_sell_order_guard_task_service.run()
            if bit2me_error_status_code == 500:
                notify_fatal_error_via_telegram_mock.assert_called()
            else:
                notify_fatal_error_via_telegram_mock.assert_not_called()

            httpserver.check_assertions()


def _prepare_httpserver_mock(
    faker: Faker,
    httpserver: HTTPServer,
    bit2me_api_key: str,
    bik2me_api_secret: str,
    bit2me_error_status_code: int | None = None,
    *,
    closing_crypto_currency_price_multipler: float,
    simulate_future_sell_orders: bool = False,
) -> list[Bit2MeOrderDto]:
    symbol = faker.random_element(["ETH/EUR", "SOL/EUR"])
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

    orders_price = faker.pyfloat(positive=True, min_value=500, max_value=1_000)
    orders_create_at = datetime.now(UTC) + timedelta(days=2) if simulate_future_sell_orders else None
    opened_sell_bit2me_orders = [
        Bit2MeOrderDtoObjectMother.create(
            created_at=orders_create_at,
            side="sell",
            symbol=symbol,
            order_type="stop-limit",
            price=orders_price,
            status=faker.random_element(["open", "inactive"]),
        ),
        Bit2MeOrderDtoObjectMother.create(
            created_at=orders_create_at,
            side="sell",
            symbol=symbol,
            order_type="limit",
            price=orders_price,
            status=faker.random_element(["open", "inactive"]),
        ),
    ]
    tickers = Bit2MeTickersDtoObjectMother.create(
        symbol=symbol, close=orders_price * closing_crypto_currency_price_multipler
    )
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
    # Mock call to /v2/trading/tickers
    httpserver.expect(
        Bit2MeAPIRequestMacher(
            "/bit2me-api/v2/trading/tickers", method="GET", query_string={"symbol": symbol}
        ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_json(RootModel[list[Bit2MeTickersDto]]([tickers]).model_dump(mode="json", by_alias=True))

    for sell_order in opened_sell_bit2me_orders:
        # Mock call to /v1/trading/trade to get closed buy trades
        if bit2me_error_status_code is not None:
            httpserver.expect(
                Bit2MeAPIRequestMacher(
                    "/bit2me-api/v1/trading/trade",
                    method="GET",
                    query_string=urlencode({"direction": "desc", "side": "buy", "symbol": symbol}, doseq=False),
                ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_response(Response(status=bit2me_error_status_code))
        # Mock trades /v1/trading/trade
        httpserver.expect(
            Bit2MeAPIRequestMacher(
                "/bit2me-api/v1/trading/trade",
                method="GET",
                query_string=urlencode({"direction": "desc", "side": "buy", "symbol": symbol}, doseq=False),
            ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
            handler_type=HandlerType.ONESHOT,
        ).respond_with_json(
            Bit2MePaginationResultDto[Bit2MeTradeDto](
                data=buy_trades, total=faker.pyint(min_value=len(buy_trades), max_value=len(buy_trades) * 10)
            ).model_dump(mode="json", by_alias=True)
        )
        if not simulate_future_sell_orders:
            # Mock call to DELETE /v1/trading/order/{id}
            httpserver.expect(
                Bit2MeAPIRequestMacher(
                    f"/bit2me-api/v1/trading/order/{str(sell_order.id)}", method="DELETE"
                ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_response(Response(status=204))

            # Mock call to POST /v1/trading/order
            httpserver.expect(
                Bit2MeAPIRequestMacher("/bit2me-api/v1/trading/order", method="POST").set_bit2me_api_key_and_secret(
                    bit2me_api_key, bik2me_api_secret
                ),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_json(
                Bit2MeOrderDtoObjectMother.create(
                    side="sell", order_type="market", status=faker.random_element(["open", "inactive"])
                ).model_dump(by_alias=True, mode="json")
            )
    return opened_sell_bit2me_orders


async def _create_fake_market_signals(first_order: Bit2MeOrderDto) -> None:
    market_signal_service = MarketSignalService()

    one_hour_last_signals = [
        SignalsEvaluationResultObjectMother.create(symbol=first_order.symbol, timeframe="1h", buy=True, sell=False),
        SignalsEvaluationResultObjectMother.create(symbol=first_order.symbol, timeframe="1h", buy=False, sell=True),
    ]
    for signal in one_hour_last_signals:
        await market_signal_service.on_signals_evaluation_result(signal)
        await asyncio.sleep(delay=2.0)
