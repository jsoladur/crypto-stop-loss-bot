import asyncio
import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import ccxt.async_support as ccxt
import pytest
from aiogram import Bot
from faker import Faker
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType

from crypto_trailing_stop.commons.constants import BIT2ME_RETRYABLE_HTTP_STATUS_CODES, PERCENT_TO_SELL_LIST
from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_order_dto import MEXCOrderDto
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange import AbstractOperatingExchangeService
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import (
    OperatingExchangeEnum,
    OrderTypeEnum,
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
from crypto_trailing_stop.infrastructure.tasks.limit_sell_order_guard_task_service import LimitSellOrderGuardTaskService
from tests.helpers.background_jobs_test_utils import disable_all_background_jobs_except
from tests.helpers.httpserver_pytest.utils import (
    prepare_httpserver_delete_order_mock,
    prepare_httpserver_fetch_ohlcv_mock,
    prepare_httpserver_open_sell_orders_mock,
    prepare_httpserver_sell_order_created_mock,
    prepare_httpserver_tickers_list_mock,
    prepare_httpserver_trades_mock,
    prepare_httpserver_trading_wallet_balances_mock,
)
from tests.helpers.object_mothers import (
    Bit2MeOrderDtoObjectMother,
    Bit2MeTickersDtoObjectMother,
    MEXCOrderDtoObjectMother,
    MEXCTickerPriceAndBookDtoObjectMother,
    SignalsEvaluationResultObjectMother,
)
from tests.helpers.operating_exchange_utils import get_random_symbol_by_operating_exchange

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
    _, httpserver, api_key, api_secret, operating_exchange, *_ = integration_test_env
    # Disable all jobs by default for test purposes!
    await disable_all_background_jobs_except()

    _, buy_prices, fetch_ohlcv_return_value, *_ = _prepare_httpserver_mock(
        faker,
        httpserver,
        operating_exchange,
        api_key,
        api_secret,
        closing_crypto_currency_price_multipler=0.495,
        percent_to_sell=percent_to_sell,
    )
    first_order_and_price, *_ = buy_prices
    first_order, buy_price = first_order_and_price
    crypto_currency, *_ = first_order.symbol.split("/")

    task_manager = get_application_container().infrastructure_container().tasks_container().task_manager()
    buy_sell_signals_config_service: BuySellSignalsConfigService = (
        get_application_container().infrastructure_container().services_container().buy_sell_signals_config_service()
    )

    buy_sell_signals_config_item: BuySellSignalsConfigItem = buy_sell_signals_config_service._get_defaults_by_symbol(
        symbol=crypto_currency
    )
    buy_sell_signals_config_item.enable_exit_on_take_profit = False
    await buy_sell_signals_config_service.save_or_update(buy_sell_signals_config_item)

    # Create fake market signals to simulate the sudden SELL 1H market signal
    await _create_fake_market_signals(first_order, closing_price_sell_1h_signal=buy_price)
    limit_sell_order_guard_cache_service = LimitSellOrderGuardCacheService()
    limit_sell_order_guard_cache_service.mark_immediate_sell_order(
        ImmediateSellOrderItem(
            sell_order_id=first_order.id if isinstance(first_order, Bit2MeOrderDto) else first_order.order_id,
            percent_to_sell=percent_to_sell,
        )
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
            if operating_exchange == OperatingExchangeEnum.MEXC:
                with patch.object(ccxt.mexc, "fetch_ohlcv", return_value=fetch_ohlcv_return_value):
                    await limit_sell_order_guard_task_service.run()
            else:
                await limit_sell_order_guard_task_service.run()

        notify_fatal_error_via_telegram_mock.assert_not_called()
    httpserver.check_assertions()


@pytest.mark.asyncio
async def should_create_market_sell_order_when_take_profit_reached(
    faker: Faker, integration_test_env: tuple[HTTPServer, str]
) -> None:
    """
    Test that all expected calls to Bit2Me are made when a limit sell order has to be filled
    """
    # Mock the Bit2Me API
    _, httpserver, api_key, api_secret, operating_exchange, *_ = integration_test_env
    # Disable all jobs by default for test purposes!
    await disable_all_background_jobs_except()

    _, buy_prices, fetch_ohlcv_return_value, *_ = _prepare_httpserver_mock(
        faker, httpserver, operating_exchange, api_key, api_secret, closing_crypto_currency_price_multipler=1.5
    )
    first_order_and_price, *_ = buy_prices
    first_order, *_ = first_order_and_price
    crypto_currency, *_ = first_order.symbol.split("/")

    task_manager = get_application_container().infrastructure_container().tasks_container().task_manager()
    buy_sell_signals_config_service: BuySellSignalsConfigService = (
        get_application_container().infrastructure_container().services_container().buy_sell_signals_config_service()
    )

    buy_sell_signals_config_item: BuySellSignalsConfigItem = buy_sell_signals_config_service._get_defaults_by_symbol(
        symbol=crypto_currency
    )
    buy_sell_signals_config_item.enable_exit_on_take_profit = True
    await buy_sell_signals_config_service.save_or_update(buy_sell_signals_config_item)

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
            if operating_exchange == OperatingExchangeEnum.MEXC:
                with patch.object(ccxt.mexc, "fetch_ohlcv", return_value=fetch_ohlcv_return_value):
                    await limit_sell_order_guard_task_service.run()
            else:
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
    _, httpserver, api_key, api_secret, operating_exchange, *_ = integration_test_env
    # Disable all jobs by default for test purposes!
    await disable_all_background_jobs_except()

    opened_sell_orders, _, fetch_ohlcv_return_value, *_ = _prepare_httpserver_mock(
        faker,
        httpserver,
        operating_exchange,
        api_key,
        api_secret,
        closing_crypto_currency_price_multipler=1.5,
        simulate_future_sell_orders=simulate_future_sell_orders,
    )
    first_order, *_ = opened_sell_orders
    crypto_currency, *_ = first_order.symbol.split("/")
    task_manager = get_application_container().infrastructure_container().tasks_container().task_manager()
    buy_sell_signals_config_service: BuySellSignalsConfigService = (
        get_application_container().infrastructure_container().services_container().buy_sell_signals_config_service()
    )

    buy_sell_signals_config_item: BuySellSignalsConfigItem = buy_sell_signals_config_service._get_defaults_by_symbol(
        symbol=crypto_currency
    )
    buy_sell_signals_config_item.enable_exit_on_take_profit = False
    await buy_sell_signals_config_service.save_or_update(buy_sell_signals_config_item)

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
            if operating_exchange == OperatingExchangeEnum.MEXC:
                with patch.object(ccxt.mexc, "fetch_ohlcv", return_value=fetch_ohlcv_return_value):
                    await limit_sell_order_guard_task_service.run()
            else:
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
    _, httpserver, api_key, api_secret, operating_exchange, *_ = integration_test_env
    # Disable all jobs by default for test purposes!
    await disable_all_background_jobs_except()

    _, buy_prices, fetch_ohlcv_return_value, *_ = _prepare_httpserver_mock(
        faker,
        httpserver,
        operating_exchange,
        api_key,
        api_secret,
        closing_crypto_currency_price_multipler=0.495,
        simulate_future_sell_orders=False,
        sell_1h_signals_behind_break_even=True,
    )
    first_order_and_price, *_ = buy_prices
    first_order, buy_price = first_order_and_price
    crypto_currency, *_ = first_order.symbol.split("/")
    task_manager = get_application_container().infrastructure_container().tasks_container().task_manager()
    buy_sell_signals_config_service: BuySellSignalsConfigService = (
        get_application_container().infrastructure_container().services_container().buy_sell_signals_config_service()
    )

    buy_sell_signals_config_item: BuySellSignalsConfigItem = buy_sell_signals_config_service._get_defaults_by_symbol(
        symbol=crypto_currency
    )
    buy_sell_signals_config_item.enable_exit_on_take_profit = False
    await buy_sell_signals_config_service.save_or_update(buy_sell_signals_config_item)

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
            if operating_exchange == OperatingExchangeEnum.MEXC:
                with patch.object(ccxt.mexc, "fetch_ohlcv", return_value=fetch_ohlcv_return_value):
                    await limit_sell_order_guard_task_service.run()
            else:
                await limit_sell_order_guard_task_service.run()
        notify_fatal_error_via_telegram_mock.assert_not_called()
    httpserver.check_assertions()


@pytest.mark.parametrize("operating_exchange_error_status_code", BIT2ME_RETRYABLE_HTTP_STATUS_CODES + [500])
@pytest.mark.asyncio
async def should_create_market_sell_order_when_stop_loss_triggered(
    faker: Faker, operating_exchange_error_status_code: int, integration_test_env: tuple[HTTPServer, str]
) -> None:
    """
    Test that all expected calls to Bit2Me are made when a limit sell order has to be filled
    """
    # Mock the Bit2Me API
    _, httpserver, api_key, api_secret, operating_exchange, *_ = integration_test_env
    # Disable all jobs by default for test purposes!
    await disable_all_background_jobs_except()
    opened_sell_orders, _, fetch_ohlcv_return_value, *_ = _prepare_httpserver_mock(
        faker,
        httpserver,
        operating_exchange,
        api_key,
        api_secret,
        operating_exchange_error_status_code=operating_exchange_error_status_code,
        closing_crypto_currency_price_multipler=0.2,
    )
    task_manager = get_application_container().infrastructure_container().tasks_container().task_manager()
    buy_sell_signals_config_service: BuySellSignalsConfigService = (
        get_application_container().infrastructure_container().services_container().buy_sell_signals_config_service()
    )

    for current_order in opened_sell_orders:
        crypto_currency, *_ = current_order.symbol.split("/")
        buy_sell_signals_config_item: BuySellSignalsConfigItem = (
            buy_sell_signals_config_service._get_defaults_by_symbol(symbol=crypto_currency)
        )
        buy_sell_signals_config_item.enable_exit_on_take_profit = False
        buy_sell_signals_config_item.enable_exit_on_sell_signal = True
        await buy_sell_signals_config_service.save_or_update(buy_sell_signals_config_item)

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
            if operating_exchange == OperatingExchangeEnum.MEXC:
                with patch.object(ccxt.mexc, "fetch_ohlcv", return_value=fetch_ohlcv_return_value):
                    await limit_sell_order_guard_task_service.run()
            else:
                await limit_sell_order_guard_task_service.run()
        notify_fatal_error_via_telegram_mock.assert_not_called()
    httpserver.check_assertions()


def _prepare_httpserver_mock(
    faker: Faker,
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    operating_exchange_error_status_code: int | None = None,
    *,
    closing_crypto_currency_price_multipler: float,
    simulate_future_sell_orders: bool = False,
    sell_1h_signals_behind_break_even: bool = False,
    percent_to_sell: float = 100.0,
) -> tuple[list[Bit2MeOrderDto], list[Bit2MeOrderDto, float]]:
    symbol = get_random_symbol_by_operating_exchange(faker, operating_exchange)
    crypto_currency, *_ = symbol.split("/")
    # Mock OHLCV /v1/trading/candle
    fetch_ohlcv_return_value = prepare_httpserver_fetch_ohlcv_mock(
        faker, httpserver, operating_exchange, api_key, api_secret, symbol, simulate_empty_ohlcv=True
    )
    orders_price = faker.pyfloat(positive=True, min_value=500, max_value=1_000)
    _prepare_httpserver_tickers_list_mock(
        faker,
        httpserver,
        operating_exchange,
        api_key,
        api_secret,
        closing_crypto_currency_price_multipler,
        symbol,
        orders_price,
    )
    # Mock call to /v1/trading/order to get opened sell orders
    opened_sell_orders = _prepare_httpserver_open_sell_orders_mock(
        faker, httpserver, operating_exchange, api_key, api_secret, simulate_future_sell_orders, symbol, orders_price
    )
    # Mock trades /v1/trading/trade
    *_, buy_prices = prepare_httpserver_trades_mock(
        faker,
        httpserver,
        operating_exchange,
        api_key,
        api_secret,
        opened_sell_orders,
        operating_exchange_error_status_code=operating_exchange_error_status_code,
    )
    for sell_order in opened_sell_orders:
        if not simulate_future_sell_orders and not sell_1h_signals_behind_break_even:
            # Mock call to DELETE /v1/trading/order/{id}
            prepare_httpserver_delete_order_mock(
                httpserver, operating_exchange, api_key, api_secret, open_sell_order=sell_order
            )
            prepare_httpserver_sell_order_created_mock(
                faker, httpserver, operating_exchange, api_key, api_secret, order_symbol=sell_order.symbol
            )
            if percent_to_sell < 100:
                operating_exchange_service: AbstractOperatingExchangeService = (
                    get_application_container().adapters_container().operating_exchange_service()
                )
                prepare_httpserver_trading_wallet_balances_mock(
                    faker,
                    httpserver,
                    operating_exchange,
                    api_key,
                    api_secret,
                    wallet_balances_crypto_currencies=[crypto_currency.upper()],
                    fixed_balance=round(
                        sell_order.order_amount
                        if isinstance(sell_order, Bit2MeOrderDto)
                        else float(sell_order.qty)
                        * ((percent_to_sell - operating_exchange_service.get_taker_fee()) / 100),
                        ndigits=2,
                    ),
                )
                prepare_httpserver_sell_order_created_mock(
                    faker,
                    httpserver,
                    operating_exchange,
                    api_key,
                    api_secret,
                    order_symbol=sell_order.symbol,
                    order_type=OrderTypeEnum.LIMIT,
                )
    return opened_sell_orders, buy_prices, fetch_ohlcv_return_value


def _prepare_httpserver_tickers_list_mock(
    faker: Faker,
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    closing_crypto_currency_price_multipler: float,
    symbol: str,
    orders_price: float,
) -> None:
    if operating_exchange == OperatingExchangeEnum.BIT2ME:
        tickers = Bit2MeTickersDtoObjectMother.create(
            symbol=symbol, close=orders_price * closing_crypto_currency_price_multipler
        )
        rest_tickers = Bit2MeTickersDtoObjectMother.list(exclude_symbols=symbol)
        tickers_list = [tickers] + rest_tickers
    elif operating_exchange == OperatingExchangeEnum.MEXC:
        tickers = MEXCTickerPriceAndBookDtoObjectMother.create(
            symbol=symbol, close=orders_price * closing_crypto_currency_price_multipler
        )
        rest_tickers = MEXCTickerPriceAndBookDtoObjectMother.list(exclude_symbols=symbol)
        tickers_list = [tickers] + rest_tickers
    prepare_httpserver_tickers_list_mock(
        faker,
        httpserver,
        operating_exchange,
        api_key,
        api_secret,
        tickers_list=tickers_list,
        handler_type=HandlerType.ONESHOT,
    )


def _prepare_httpserver_open_sell_orders_mock(
    faker: Faker,
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    simulate_future_sell_orders: bool,
    symbol: str,
    orders_price: float,
) -> list[Bit2MeOrderDto] | list[MEXCOrderDto]:
    orders_create_at = datetime.now(UTC) + timedelta(days=2) if simulate_future_sell_orders else None
    if operating_exchange == OperatingExchangeEnum.BIT2ME:
        opened_sell_orders = [
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
    elif operating_exchange == OperatingExchangeEnum.MEXC:
        opened_sell_orders = [
            MEXCOrderDtoObjectMother.create(
                created_at=orders_create_at,
                side="SELL",
                symbol=symbol,
                order_type="STOP_LIMIT",
                price=orders_price,
                status="NEW",
            ),
            MEXCOrderDtoObjectMother.create(
                created_at=orders_create_at,
                side="SELL",
                symbol=symbol,
                order_type="LIMIT",
                price=orders_price,
                status="NEW",
            ),
        ]
    prepare_httpserver_open_sell_orders_mock(
        faker, httpserver, operating_exchange, api_key, api_secret, symbol, opened_sell_orders=opened_sell_orders
    )

    return opened_sell_orders


async def _create_fake_market_signals(
    first_order: Bit2MeOrderDto, *, closing_price_sell_1h_signal: float | None = None, bearish_divergence: bool = False
) -> None:
    market_signal_service: MarketSignalService = (
        get_application_container().infrastructure_container().services_container().market_signal_service()
    )

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
