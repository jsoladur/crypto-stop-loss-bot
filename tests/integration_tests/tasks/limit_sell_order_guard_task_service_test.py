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

from crypto_trailing_stop.commons.constants import BIT2ME_TAKER_FEES, PERCENT_TO_SELL_LIST
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_pagination_result_dto import Bit2MePaginationResultDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_trade_dto import Bit2MeTradeDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_trading_wallet_balance import (
    Bit2MeTradingWalletBalanceDto,
)
from crypto_trailing_stop.infrastructure.database.models.push_notification import PushNotification
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.enums.global_flag_enum import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.enums.push_notification_type_enum import PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.limit_sell_order_guard_cache_service import (
    LimitSellOrderGuardCacheService,
)
from crypto_trailing_stop.infrastructure.services.market_signal_service import MarketSignalService
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.infrastructure.services.vo.immediate_sell_order_item import ImmediateSellOrderItem
from crypto_trailing_stop.infrastructure.tasks import get_task_manager_instance
from crypto_trailing_stop.infrastructure.tasks.limit_sell_order_guard_task_service import LimitSellOrderGuardTaskService
from tests.helpers.background_jobs_test_utils import disable_all_background_jobs_except
from tests.helpers.httpserver_pytest import Bit2MeAPIQueryMatcher, Bit2MeAPIRequestMacher
from tests.helpers.object_mothers import (
    Bit2MeOrderDtoObjectMother,
    Bit2MeTickersDtoObjectMother,
    Bit2MeTradingWalletBalanceDtoObjectMother,
    SignalsEvaluationResultObjectMother,
)
from tests.helpers.ohlcv_test_utils import get_fetch_ohlcv_random_result
from tests.helpers.sell_orders_test_utils import generate_trades

logger = logging.getLogger(__name__)


@pytest.mark.parametrize("percent_to_sell", PERCENT_TO_SELL_LIST[::-1])
@pytest.mark.asyncio
async def should_create_market_sell_order_when_market_for_immediate_sell_order(
    faker: Faker, percent_to_sell: float, integration_test_env: tuple[HTTPServer, str]
) -> None:
    """
    Test that all expected calls to Bit2Me are made when a limit sell order has to be filled
    """
    # Mock the Bit2Me API
    _, httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_env
    # Disable all jobs by default for test purposes!
    await disable_all_background_jobs_except()

    *_, buy_prices = _prepare_httpserver_mock(
        faker,
        httpserver,
        bit2me_api_key,
        bit2me_api_secret,
        closing_crypto_currency_price_multipler=0.495,
        percent_to_sell=percent_to_sell,
    )
    first_order_and_price, *_ = buy_prices
    first_order, buy_price = first_order_and_price
    crypto_currency, *_ = first_order.symbol.split("/")
    await BuySellSignalsConfigService().save_or_update(
        BuySellSignalsConfigItem(symbol=crypto_currency, auto_exit_atr_take_profit=False)
    )
    task_manager = get_task_manager_instance()

    # Create fake market signals to simulate the sudden SELL 1H market signal

    await _create_fake_market_signals(first_order, closing_price_sell_1h_signal=buy_price)
    limit_sell_order_guard_cache_service = LimitSellOrderGuardCacheService()
    limit_sell_order_guard_cache_service.mark_immediate_sell_order(
        ImmediateSellOrderItem(sell_order_id=first_order.id, percent_to_sell=percent_to_sell)
    )

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
    await disable_all_background_jobs_except()

    _prepare_httpserver_mock(
        faker, httpserver, bit2me_api_key, bit2me_api_secret, closing_crypto_currency_price_multipler=1.5
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

            notify_fatal_error_via_telegram_mock.assert_not_called()
            httpserver.check_assertions()


@pytest.mark.parametrize(
    "simulate_future_sell_orders,bearish_divergence",
    [(bool1, bool2) for bool1 in [True, False] for bool2 in [True, False]],
)
@pytest.mark.asyncio
async def should_create_market_sell_order_when_auto_exit_sell_or_bearish_divergence_1h_signal(
    faker: Faker,
    simulate_future_sell_orders: bool,
    bearish_divergence: bool,
    integration_test_env: tuple[HTTPServer, str],
) -> None:
    """
    Test that all expected calls to Bit2Me are made when a limit sell order has to be filled
    """
    # Mock the Bit2Me API
    _, httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_env
    # Disable all jobs by default for test purposes!
    await disable_all_background_jobs_except()

    opened_sell_bit2me_orders, *_ = _prepare_httpserver_mock(
        faker,
        httpserver,
        bit2me_api_key,
        bit2me_api_secret,
        closing_crypto_currency_price_multipler=1.5,
        simulate_future_sell_orders=simulate_future_sell_orders,
    )
    first_order, *_ = opened_sell_bit2me_orders
    crypto_currency, *_ = first_order.symbol.split("/")
    await BuySellSignalsConfigService().save_or_update(
        BuySellSignalsConfigItem(symbol=crypto_currency, auto_exit_atr_take_profit=False)
    )
    task_manager = get_task_manager_instance()

    # Create fake market signals to simulate the sudden SELL 1H market signal
    await _create_fake_market_signals(first_order, bearish_divergence=bearish_divergence)

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


@pytest.mark.asyncio
async def should_ignore_sell_1h_signal_and_not_sell_when_price_is_lower_than_break_even(
    faker: Faker, integration_test_env: tuple[HTTPServer, str]
) -> None:
    """
    Test that all expected calls to Bit2Me are made when a limit sell order has to be filled
    """
    # Mock the Bit2Me API
    _, httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_env
    # Disable all jobs by default for test purposes!
    await disable_all_background_jobs_except()

    *_, buy_prices = _prepare_httpserver_mock(
        faker,
        httpserver,
        bit2me_api_key,
        bit2me_api_secret,
        closing_crypto_currency_price_multipler=0.495,
        simulate_future_sell_orders=False,
        sell_1h_signals_behind_break_even=True,
    )
    first_order_and_price, *_ = buy_prices
    first_order, buy_price = first_order_and_price
    crypto_currency, *_ = first_order.symbol.split("/")
    await BuySellSignalsConfigService().save_or_update(
        BuySellSignalsConfigItem(symbol=crypto_currency, auto_exit_atr_take_profit=False)
    )
    task_manager = get_task_manager_instance()

    # Create fake market signals to simulate the sudden SELL 1H market signal

    await _create_fake_market_signals(first_order, closing_price_sell_1h_signal=buy_price)

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


@pytest.mark.parametrize("bit2me_error_status_code", [403, 412, 429, 500, 502])
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
    await disable_all_background_jobs_except()
    opened_sell_bit2me_orders, *_ = _prepare_httpserver_mock(
        faker,
        httpserver,
        bit2me_api_key,
        bit2me_api_secret,
        bit2me_error_status_code=bit2me_error_status_code,
        closing_crypto_currency_price_multipler=0.2,
    )
    for current_order in opened_sell_bit2me_orders:
        crypto_currency, *_ = current_order.symbol.split("/")
        await BuySellSignalsConfigService().save_or_update(
            BuySellSignalsConfigItem(symbol=crypto_currency, auto_exit_sell_1h=False, auto_exit_atr_take_profit=False)
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
    sell_1h_signals_behind_break_even: bool = False,
    percent_to_sell: float = 100.0,
) -> tuple[list[Bit2MeOrderDto], list[Bit2MeOrderDto, float]]:
    symbol = faker.random_element(["ETH/EUR", "SOL/EUR"])
    crypto_currency, *_ = symbol.split("/")
    # Mock OHLCV /v1/trading/candle
    fetch_ohlcv_return_value = get_fetch_ohlcv_random_result(faker)
    # Simulate that some times the Bit2Me API returns an empty list
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
    ).respond_with_json([])
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
    rest_tickers = Bit2MeTickersDtoObjectMother.list(exclude_symbols=symbol)
    tickers_list = [tickers] + rest_tickers
    buy_trades, buy_prices = generate_trades(faker, opened_sell_bit2me_orders)
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
        Bit2MeAPIRequestMacher("/bit2me-api/v2/trading/tickers", method="GET").set_bit2me_api_key_and_secret(
            bit2me_api_key, bik2me_api_secret
        ),
        handler_type=HandlerType.ONESHOT,
    ).respond_with_json(RootModel[list[Bit2MeTickersDto]](tickers_list).model_dump(mode="json", by_alias=True))

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
        if not simulate_future_sell_orders and not sell_1h_signals_behind_break_even:
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

            if percent_to_sell < 100:
                httpserver.expect(
                    Bit2MeAPIRequestMacher(
                        "/bit2me-api/v1/trading/wallet/balance",
                        query_string=urlencode({"symbols": crypto_currency.upper()}, doseq=False),
                        method="GET",
                    ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
                    handler_type=HandlerType.ONESHOT,
                ).respond_with_json(
                    RootModel[list[Bit2MeTradingWalletBalanceDto]](
                        [
                            Bit2MeTradingWalletBalanceDtoObjectMother.create(
                                currency=crypto_currency,
                                balance=round(
                                    sell_order.order_amount * ((percent_to_sell - BIT2ME_TAKER_FEES) / 100), ndigits=2
                                ),
                            )
                        ]
                    ).model_dump(mode="json", by_alias=True)
                )
                httpserver.expect(
                    Bit2MeAPIRequestMacher("/bit2me-api/v1/trading/order", method="POST").set_bit2me_api_key_and_secret(
                        bit2me_api_key, bik2me_api_secret
                    ),
                    handler_type=HandlerType.ONESHOT,
                ).respond_with_json(
                    Bit2MeOrderDtoObjectMother.create(side="sell", order_type="limit", status="open").model_dump(
                        by_alias=True, mode="json"
                    )
                )

    return opened_sell_bit2me_orders, buy_prices


async def _create_fake_market_signals(
    first_order: Bit2MeOrderDto, *, closing_price_sell_1h_signal: float | None = None, bearish_divergence: bool = False
) -> None:
    market_signal_service = MarketSignalService()

    one_hour_last_signals = [
        SignalsEvaluationResultObjectMother.create(symbol=first_order.symbol, timeframe="1h", buy=True, sell=False),
        SignalsEvaluationResultObjectMother.create(
            symbol=first_order.symbol,
            timeframe="1h",
            buy=False,
            sell=not bearish_divergence,
            bearish_divergence=bearish_divergence,
            closing_price=closing_price_sell_1h_signal,
        ),
    ]
    for signal in one_hour_last_signals:
        await market_signal_service.on_signals_evaluation_result(signal)
        await asyncio.sleep(delay=2.0)
