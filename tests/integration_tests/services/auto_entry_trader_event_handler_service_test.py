import asyncio
import logging
import math
from datetime import UTC, datetime
from itertools import product
from unittest.mock import patch

import ccxt.async_support as ccxt
import pytest
from aiogram import Bot
from faker import Faker
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType

from crypto_trailing_stop.commons.constants import TRIGGER_BUY_ACTION_EVENT_NAME
from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_order_dto import CreateNewMEXCOrderDto, MEXCOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_ticker_book_dto import MEXCTickerBookDto
from crypto_trailing_stop.infrastructure.adapters.dtos.mexc_ticker_price_dto import MEXCTickerPriceDto
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.base import AbstractOperatingExchangeService
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import OperatingExchangeEnum
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo.symbol_market_config import (
    SymbolMarketConfig,
)
from crypto_trailing_stop.infrastructure.database.models.push_notification import PushNotification
from crypto_trailing_stop.infrastructure.services.auto_buy_trader_config_service import AutoBuyTraderConfigService
from crypto_trailing_stop.infrastructure.services.auto_entry_trader_event_handler_service import (
    AutoEntryTraderEventHandlerService,
)
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.enums.global_flag_enum import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.enums.push_notification_type_enum import PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.vo.auto_buy_trader_config_item import AutoBuyTraderConfigItem
from crypto_trailing_stop.infrastructure.services.vo.market_signal_item import MarketSignalItem
from tests.helpers.background_jobs_test_utils import disable_all_background_jobs_except
from tests.helpers.enums import AutoEntryTraderUnexpectedErrorBuyMarketOrder, AutoEntryTraderWarningTypeEnum
from tests.helpers.httpserver_pytest import Bit2MeAPIRequestMatcher, CustomAPIQueryMatcher, MEXCAPIRequestMatcher
from tests.helpers.httpserver_pytest.utils import (
    prepare_httpserver_fetch_ohlcv_mock,
    prepare_httpserver_open_sell_orders_mock,
    prepare_httpserver_retrieve_portfolio_balance_mock,
    prepare_httpserver_tickers_list_mock,
    prepare_httpserver_trades_mock,
    prepare_httpserver_trading_wallet_balances_mock,
)
from tests.helpers.market_config_test_utils import get_symbol_market_config_by_exchange_and_symbol
from tests.helpers.object_mothers import (
    Bit2MeOrderDtoObjectMother,
    Bit2MeTickersDtoObjectMother,
    Bit2MeTradeDtoObjectMother,
    MEXCOrderDtoObjectMother,
    MEXCTickerPriceAndBookDtoObjectMother,
    MEXCTradeDtoObjectMother,
)
from tests.helpers.operating_exchange_utils import get_random_symbol_by_operating_exchange

logger = logging.getLogger(__name__)


use_cases_no_event_emitter = list(
    product(
        [False],  # use_event_emitter
        list(AutoEntryTraderWarningTypeEnum),
        list(AutoEntryTraderUnexpectedErrorBuyMarketOrder),
    )
)
use_cases_event_emitter = list(
    product(
        [True],  # use_event_emitter
        list(AutoEntryTraderWarningTypeEnum),
        [AutoEntryTraderUnexpectedErrorBuyMarketOrder.NONE],
    )
)
use_cases = use_cases_no_event_emitter + use_cases_event_emitter
use_cases = [
    (use_event_emitter, bool(idx % 2), warning_type, unexpected_error_buy_market_order)
    for idx, (use_event_emitter, warning_type, unexpected_error_buy_market_order) in enumerate(use_cases)
]


@pytest.mark.parametrize(
    "use_event_emitter,enable_atr_auto_take_profit,warning_type,unexpected_error_buy_market_order", use_cases
)
@pytest.mark.asyncio
async def should_create_market_buy_order_and_limit_sell_when_market_buy_1h_signal_is_triggered(
    faker: Faker,
    use_event_emitter: bool,
    warning_type: AutoEntryTraderWarningTypeEnum,
    unexpected_error_buy_market_order: AutoEntryTraderUnexpectedErrorBuyMarketOrder,
    enable_atr_auto_take_profit: bool,
    integration_test_env: tuple[HTTPServer, str],
) -> None:
    """
    Test that all expected calls to Bit2Me are made when a limit sell order has to be filled
    """
    # Mock the Bit2Me API
    _, httpserver, api_key, api_secret, operating_exchange, *_ = integration_test_env

    # Disable all jobs by default for test purposes!
    await disable_all_background_jobs_except(exclusion=[GlobalFlagTypeEnum.AUTO_ENTRY_TRADER])

    auto_buy_trader_config_service: AutoBuyTraderConfigService = (
        get_application_container().infrastructure_container().services_container().auto_buy_trader_config_service()
    )
    buy_sell_signals_config_service: BuySellSignalsConfigService = (
        get_application_container().infrastructure_container().services_container().buy_sell_signals_config_service()
    )

    global_flag_service: GlobalFlagService = (
        get_application_container().infrastructure_container().services_container().global_flag_service()
    )
    market_signal_item, _, crypto_currency, _, fetch_ohlcv_return_value, *_ = _prepare_httpserver_mock(
        faker,
        httpserver,
        operating_exchange,
        api_key,
        api_secret,
        use_event_emitter=use_event_emitter,
        warning_type=warning_type,
        unexpected_error_buy_market_order=unexpected_error_buy_market_order,
    )
    if not enable_atr_auto_take_profit:
        buy_sell_signals_config_item = buy_sell_signals_config_service._get_defaults_by_symbol(symbol=crypto_currency)
        buy_sell_signals_config_item.enable_exit_on_take_profit = False
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

    # Persist 100% FIAT asssigned to the symbol
    await auto_buy_trader_config_service.save_or_update(
        AutoBuyTraderConfigItem(symbol=crypto_currency, fiat_wallet_percent_assigned=100)
    )
    # Trigger the event
    with patch.object(GlobalFlagService, "_toggle_task") as toggle_task_mock:
        with patch.object(
            AutoEntryTraderEventHandlerService, "_notify_fatal_error_via_telegram"
        ) as notify_fatal_error_via_telegram_mock:
            with patch.object(Bot, "send_message"):
                if operating_exchange == OperatingExchangeEnum.MEXC:
                    with patch.object(ccxt.mexc, "fetch_ohlcv", return_value=fetch_ohlcv_return_value):
                        await _exec_test(use_event_emitter, market_signal_item)
                else:
                    await _exec_test(use_event_emitter, market_signal_item)

            httpserver.check_assertions()

            notify_fatal_error_via_telegram_mock.assert_not_called()
            if warning_type == AutoEntryTraderWarningTypeEnum.NONE:
                toggle_task_mock.assert_called()

                is_enabled_for_limit_sell_order_guard = await global_flag_service.is_enabled_for(
                    GlobalFlagTypeEnum.LIMIT_SELL_ORDER_GUARD
                )
                assert is_enabled_for_limit_sell_order_guard is True

                buy_sell_signals_config = await buy_sell_signals_config_service.find_by_symbol(crypto_currency)
                assert buy_sell_signals_config.enable_exit_on_sell_signal is True
            else:
                toggle_task_mock.assert_not_called()


async def _exec_test(use_event_emitter: bool, market_signal_item: MarketSignalItem) -> None:
    if use_event_emitter:
        event_emitter = get_application_container().infrastructure_container().event_emitter()
        event_emitter.emit(TRIGGER_BUY_ACTION_EVENT_NAME, market_signal_item)
        await asyncio.sleep(delay=15.0)
    else:
        auto_entry_trader_event_handler_service: AutoEntryTraderEventHandlerService = (
            get_application_container()
            .infrastructure_container()
            .services_container()
            .auto_entry_trader_event_handler_service()
        )
        await auto_entry_trader_event_handler_service.on_buy_market_signal(market_signal_item)


def _prepare_httpserver_mock(
    faker: Faker,
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    *,
    use_event_emitter: bool = False,
    warning_type: AutoEntryTraderWarningTypeEnum,
    unexpected_error_buy_market_order: AutoEntryTraderUnexpectedErrorBuyMarketOrder,
) -> tuple[str, str, str]:
    symbol = get_random_symbol_by_operating_exchange(faker, operating_exchange)
    trading_market_config = get_symbol_market_config_by_exchange_and_symbol(operating_exchange, symbol)
    crypto_currency, fiat_currency = symbol.split("/")
    closing_price = faker.pyfloat(min_value=2_000, max_value=2_200)
    market_signal_item = MarketSignalItem(
        timestamp=datetime.now(UTC),
        symbol=symbol,
        timeframe="1h",
        signal_type="buy",
        rsi_state="neutral",
        atr=(closing_price * 0.9)
        if warning_type == AutoEntryTraderWarningTypeEnum.ATR_TOO_HIGH
        else faker.pyfloat(min_value=100.0, max_value=200.0),
        closing_price=closing_price,
        ema_long_price=closing_price * 0.9,
    )
    fetch_ohlcv_return_value = prepare_httpserver_fetch_ohlcv_mock(
        faker, httpserver, operating_exchange, api_key, api_secret, symbol
    )
    if warning_type != AutoEntryTraderWarningTypeEnum.ATR_TOO_HIGH:
        global_portfolio_balance = faker.pyfloat(min_value=2_500, max_value=2_700)
        spot_balance = (
            faker.pyfloat(min_value=1, max_value=20)
            if warning_type == AutoEntryTraderWarningTypeEnum.NOT_ENOUGH_FUNDS
            else (global_portfolio_balance * 0.9)
        )
        prepare_httpserver_retrieve_portfolio_balance_mock(
            faker,
            httpserver,
            operating_exchange,
            api_key,
            api_secret,
            user_currency=fiat_currency,
            global_portfolio_balance=global_portfolio_balance,
        )
        # Mock tickers
        tickers, buy_order_amount = _prepare_httpserver_tickers_mock(
            faker,
            httpserver,
            operating_exchange,
            api_key,
            api_secret,
            symbol,
            trading_market_config,
            closing_price,
            spot_balance,
        )
        # Simulate previous orders
        opened_sell_orders = _prepare_httpserver_open_sell_orders_mock(
            faker,
            httpserver,
            operating_exchange,
            api_key,
            api_secret,
            symbol,
            trading_market_config,
            closing_price,
            spot_balance,
        )
        prepare_httpserver_trades_mock(
            faker, httpserver, operating_exchange, api_key, api_secret, opened_sell_orders, number_of_trades=1
        )
        prepare_httpserver_trading_wallet_balances_mock(
            faker,
            httpserver,
            operating_exchange,
            api_key,
            api_secret,
            wallet_balances_crypto_currencies=[fiat_currency],
            fixed_balance=round(spot_balance, ndigits=2),
        )

        if warning_type != AutoEntryTraderWarningTypeEnum.NOT_ENOUGH_FUNDS:
            # Mock call to POST /v1/trading/order
            if operating_exchange == OperatingExchangeEnum.BIT2ME:
                buy_order_created = Bit2MeOrderDtoObjectMother.create(
                    symbol=symbol, side="buy", order_amount=buy_order_amount, order_type="market", status="open"
                )
            else:
                buy_order_created = MEXCOrderDtoObjectMother.create(
                    symbol=symbol, side="BUY", order_amount=buy_order_amount, order_type="MARKET", status="NEW"
                )
            _simulate_bit2me_corner_cases_if_needed(
                httpserver,
                operating_exchange,
                api_key,
                api_secret,
                use_event_emitter,
                unexpected_error_buy_market_order,
                buy_order_created,
            )
            # Buy market order created
            _prepare_httpserver_mock_order_created_successfully(
                httpserver, operating_exchange, api_key, api_secret, buy_order_created
            )
            _prepare_httpserver_mock_for_simulate_waiting_for_buy_order_filled(
                faker, httpserver, operating_exchange, api_key, api_secret, buy_order_created
            )

            operating_exchange_service: AbstractOperatingExchangeService = (
                get_application_container().adapters_container().operating_exchange_service()
            )
            buy_order_amount_after_feeds = buy_order_amount * (1 - operating_exchange_service.get_taker_fee())
            # Trading Wallet Balance for CRYPTO currency
            prepare_httpserver_trading_wallet_balances_mock(
                faker,
                httpserver,
                operating_exchange,
                api_key,
                api_secret,
                wallet_balances_crypto_currencies=[crypto_currency.upper()],
                fixed_balance=buy_order_amount_after_feeds,
            )
            # Mock Limit Sell order created
            open_sell_order = _prepare_httpserver_limit_sell_order_created_mock(
                httpserver, operating_exchange, api_key, api_secret, symbol, tickers, buy_order_amount_after_feeds
            )
            _prepare_httpserver_last_buy_trade_generated_mock(
                faker,
                httpserver,
                operating_exchange,
                api_key,
                api_secret,
                market_signal_item,
                tickers,
                buy_order_amount_after_feeds,
                open_sell_order,
            )
    return market_signal_item, symbol, crypto_currency, fiat_currency, fetch_ohlcv_return_value


def _prepare_httpserver_tickers_mock(
    faker: Faker,
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    symbol: str,
    trading_market_config: SymbolMarketConfig,
    closing_price: float,
    spot_balance: float,
) -> tuple[Bit2MeTickersDto | tuple[MEXCTickerPriceDto, MEXCTickerBookDto], float]:
    if operating_exchange == OperatingExchangeEnum.BIT2ME:
        tickers = Bit2MeTickersDtoObjectMother.create(symbol=symbol, close=closing_price * 1.02)
        rest_tickers = Bit2MeTickersDtoObjectMother.list(exclude_symbols=symbol)
        tickers_list = [tickers] + rest_tickers
        buy_order_amount = _floor_round(
            spot_balance / (tickers.ask or tickers.close), ndigits=trading_market_config.amount_precision
        )
    elif operating_exchange == OperatingExchangeEnum.MEXC:
        tickers = MEXCTickerPriceAndBookDtoObjectMother.create(symbol=symbol, close=closing_price * 1.02)
        rest_tickers = MEXCTickerPriceAndBookDtoObjectMother.list(exclude_symbols=symbol)
        tickers_list = [tickers] + rest_tickers
        ticker_price, ticker_book = tickers
        buy_order_amount = _floor_round(
            spot_balance / (ticker_book.ask_price or ticker_price.price), ndigits=trading_market_config.amount_precision
        )
    prepare_httpserver_tickers_list_mock(
        faker,
        httpserver,
        operating_exchange,
        api_key,
        api_secret,
        tickers_list=tickers_list,
        unique_tickers=[tickers],
        handler_type=HandlerType.PERMANENT,
    )
    return tickers, buy_order_amount


def _prepare_httpserver_open_sell_orders_mock(
    faker: Faker,
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    symbol: str,
    trading_market_config: SymbolMarketConfig,
    closing_price: float,
    spot_balance: float,
) -> list[Bit2MeOrderDto] | list[MEXCOrderDto]:
    previous_order_avg_buy_price = closing_price * 0.85
    if operating_exchange == OperatingExchangeEnum.BIT2ME:
        opened_sell_orders = [
            Bit2MeOrderDtoObjectMother.create(
                created_at=faker.past_datetime(tzinfo=UTC),
                side="sell",
                symbol=symbol,
                order_type="limit",
                order_amount=_floor_round(
                    (spot_balance * 0.01) / previous_order_avg_buy_price, ndigits=trading_market_config.amount_precision
                ),
                price=(closing_price * 0.9) * 2,
                status=faker.random_element(["open", "inactive"]),
            ),
            Bit2MeOrderDtoObjectMother.create(
                created_at=faker.past_datetime(tzinfo=UTC),
                side="sell",
                symbol=symbol,
                order_type="limit",
                order_amount=_floor_round(
                    (spot_balance * 0.02) / previous_order_avg_buy_price, ndigits=trading_market_config.amount_precision
                ),
                price=(closing_price * 0.92) * 2,
                status=faker.random_element(["open", "inactive"]),
            ),
        ]
    elif operating_exchange == OperatingExchangeEnum.MEXC:
        opened_sell_orders = [
            MEXCOrderDtoObjectMother.create(
                created_at=faker.past_datetime(tzinfo=UTC),
                side="SELL",
                symbol=symbol,
                order_type="LIMIT",
                order_amount=_floor_round(
                    (spot_balance * 0.01) / previous_order_avg_buy_price, ndigits=trading_market_config.amount_precision
                ),
                price=(closing_price * 0.9) * 2,
                status="NEW",
            ),
            MEXCOrderDtoObjectMother.create(
                created_at=faker.past_datetime(tzinfo=UTC),
                side="SELL",
                symbol=symbol,
                order_type="LIMIT",
                order_amount=_floor_round(
                    (spot_balance * 0.02) / previous_order_avg_buy_price, ndigits=trading_market_config.amount_precision
                ),
                price=(closing_price * 0.92) * 2,
                status="NEW",
            ),
        ]
    else:
        raise ValueError(f"Unknown operating exchange: {operating_exchange}")
    prepare_httpserver_open_sell_orders_mock(
        faker, httpserver, operating_exchange, api_key, api_secret, symbol, opened_sell_orders=opened_sell_orders
    )

    return opened_sell_orders


def _simulate_bit2me_corner_cases_if_needed(
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    use_event_emitter: bool,
    unexpected_error_buy_market_order: AutoEntryTraderUnexpectedErrorBuyMarketOrder,
    buy_order_created: Bit2MeOrderDto,
) -> None:
    if operating_exchange == OperatingExchangeEnum.BIT2ME and not use_event_emitter:
        if unexpected_error_buy_market_order == AutoEntryTraderUnexpectedErrorBuyMarketOrder.NOT_ENOUGH_BALANCE:
            _prepare_httpserver_mock_for_simulate_not_enough_balance(httpserver, api_key, api_secret)
        elif (
            unexpected_error_buy_market_order
            == AutoEntryTraderUnexpectedErrorBuyMarketOrder.SUDDEN_CANCELLED_BUY_MARKET_ORDER
        ):
            # Simulating order has been suddenly cancelled by Bit2Me exchange
            for _ in range(4):
                # Buy market order created
                _prepare_httpserver_mock_order_created_successfully(
                    httpserver, operating_exchange, api_key, api_secret, buy_order_created
                )
                httpserver.expect(
                    Bit2MeAPIRequestMatcher(
                        f"/bit2me-api/v1/trading/order/{buy_order_created.id}", method="GET"
                    ).set_api_key_and_secret(api_key, api_secret),
                    handler_type=HandlerType.ONESHOT,
                ).respond_with_json(
                    buy_order_created.model_copy(deep=True, update={"status": "cancelled"}).model_dump(
                        by_alias=True, mode="json"
                    )
                )


def _prepare_httpserver_mock_order_created_successfully(
    httpserver: HTTPServer,
    operting_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    buy_order_created: Bit2MeOrderDto | MEXCOrderDto,
) -> None:
    match operting_exchange:
        case OperatingExchangeEnum.BIT2ME:
            httpserver.expect(
                Bit2MeAPIRequestMatcher("/bit2me-api/v1/trading/order", method="POST").set_api_key_and_secret(
                    api_key, api_secret
                ),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_json(buy_order_created.model_dump(by_alias=True, mode="json"))
        case OperatingExchangeEnum.MEXC:
            additional_required_query_params = [*CreateNewMEXCOrderDto.model_fields.keys(), "signature", "timestamp"]
            httpserver.expect(
                MEXCAPIRequestMatcher(
                    "/mexc-api/api/v3/order",
                    query_string=CustomAPIQueryMatcher(
                        additional_required_query_params=additional_required_query_params
                    ),
                    method="POST",
                ).set_api_key_and_secret(api_key, api_secret),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_json(buy_order_created.model_dump(by_alias=True, mode="json"))
        case _:
            raise ValueError(f"Unknown operating exchange: {operting_exchange}")


def _prepare_httpserver_limit_sell_order_created_mock(
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    symbol: str,
    tickers: list[Bit2MeTickersDto] | list[tuple[MEXCTickerPriceDto, MEXCTickerBookDto]],
    buy_order_amount_after_feeds: float,
) -> Bit2MeOrderDto | MEXCOrderDto:
    match operating_exchange:
        case OperatingExchangeEnum.BIT2ME:
            open_sell_order = Bit2MeOrderDtoObjectMother.create(
                symbol=symbol,
                side="sell",
                order_amount=buy_order_amount_after_feeds,
                order_type="limit",
                status="open",
                price=tickers.close * 2,
            )
            httpserver.expect(
                Bit2MeAPIRequestMatcher("/bit2me-api/v1/trading/order", method="POST").set_api_key_and_secret(
                    api_key, api_secret
                ),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_json(open_sell_order.model_dump(by_alias=True, mode="json"))
        case OperatingExchangeEnum.MEXC:
            additional_required_query_params = [*CreateNewMEXCOrderDto.model_fields.keys(), "signature", "timestamp"]
            ticker_price, _ = tickers
            open_sell_order = MEXCOrderDtoObjectMother.create(
                symbol=symbol,
                side="SELL",
                order_amount=buy_order_amount_after_feeds,
                order_type="LIMIT",
                status="NEW",
                price=ticker_price.price * 2,
            )
            httpserver.expect(
                MEXCAPIRequestMatcher(
                    "/mexc-api/api/v3/order",
                    query_string=CustomAPIQueryMatcher(
                        additional_required_query_params=additional_required_query_params
                    ),
                    method="POST",
                ).set_api_key_and_secret(api_key, api_secret),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_json(open_sell_order.model_dump(by_alias=True, mode="json"))

        case _:
            raise ValueError(f"Unknown operating exchange: {operating_exchange}")
    return open_sell_order


def _prepare_httpserver_last_buy_trade_generated_mock(
    faker: Faker,
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    market_signal_item: MarketSignalItem,
    tickers: list[Bit2MeTickersDto] | list[tuple[MEXCTickerPriceDto, MEXCTickerBookDto]],
    buy_order_amount_after_feeds: float,
    open_sell_order: Bit2MeOrderDto | MEXCOrderDto,
) -> None:
    if operating_exchange == OperatingExchangeEnum.BIT2ME:
        buy_trade = Bit2MeTradeDtoObjectMother.create(
            side="buy", symbol=market_signal_item.symbol, price=tickers.close, amount=buy_order_amount_after_feeds
        )
    elif operating_exchange == OperatingExchangeEnum.MEXC:
        buy_trade = MEXCTradeDtoObjectMother.create(
            is_buyer=True, symbol=market_signal_item.symbol, price=tickers[0].price, amount=buy_order_amount_after_feeds
        )
    else:
        raise ValueError(f"Unknown operating exchange: {operating_exchange}")
    prepare_httpserver_trades_mock(
        faker,
        httpserver,
        operating_exchange,
        api_key,
        api_secret,
        [open_sell_order],
        buy_trades=[buy_trade],
        number_of_trades=1,
    )


def _prepare_httpserver_mock_for_simulate_not_enough_balance(
    httpserver: HTTPServer, api_key: str, api_secret: str
) -> None:
    # Simulation of NOT_ENOUGH_BALANCE error the first time we try to create the order
    for _ in range(7):
        httpserver.expect(
            Bit2MeAPIRequestMatcher("/bit2me-api/v1/trading/order", method="POST").set_api_key_and_secret(
                api_key, api_secret
            ),
            handler_type=HandlerType.ONESHOT,
        ).respond_with_json(
            {
                "statusCode": 412,
                "error": "Precondition Failed",
                "message": "Not enough balance in the wallet",
                "errorPayload": {"code": "NOT_ENOUGH_BALANCE"},
            },
            status=412,
        )


def _prepare_httpserver_mock_for_simulate_waiting_for_buy_order_filled(
    faker: Faker,
    httpserver: HTTPServer,
    operating_exchange: OperatingExchangeEnum,
    api_key: str,
    api_secret: str,
    buy_order_created: Bit2MeOrderDto | MEXCOrderDto,
) -> None:
    match operating_exchange:
        case OperatingExchangeEnum.BIT2ME:
            # Simulating waiting for FILLED
            for _ in range(faker.pyint(min_value=1, max_value=3)):
                httpserver.expect(
                    Bit2MeAPIRequestMatcher(
                        f"/bit2me-api/v1/trading/order/{buy_order_created.id}", method="GET"
                    ).set_api_key_and_secret(api_key, api_secret),
                    handler_type=HandlerType.ONESHOT,
                ).respond_with_json(buy_order_created.model_dump(by_alias=True, mode="json"))
            # Already filled!
            httpserver.expect(
                Bit2MeAPIRequestMatcher(
                    f"/bit2me-api/v1/trading/order/{buy_order_created.id}", method="GET"
                ).set_api_key_and_secret(api_key, api_secret),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_json(
                buy_order_created.model_copy(deep=True, update={"status": "filled"}).model_dump(
                    by_alias=True, mode="json"
                )
            )
        case OperatingExchangeEnum.MEXC:
            # Simulating waiting for FILLED
            for _ in range(faker.pyint(min_value=1, max_value=3)):
                httpserver.expect(
                    MEXCAPIRequestMatcher(
                        "/mexc-api/api/v3/order",
                        query_string=CustomAPIQueryMatcher(
                            {"orderId": str(buy_order_created.order_id)},
                            additional_required_query_params=["signature", "timestamp"],
                        ),
                        method="GET",
                    ).set_api_key_and_secret(api_key, api_secret),
                    handler_type=HandlerType.ONESHOT,
                ).respond_with_json(buy_order_created.model_dump(by_alias=True, mode="json"))
            httpserver.expect(
                MEXCAPIRequestMatcher(
                    "/mexc-api/api/v3/order",
                    query_string=CustomAPIQueryMatcher(
                        {"orderId": str(buy_order_created.order_id)},
                        additional_required_query_params=["signature", "timestamp"],
                    ),
                    method="GET",
                ).set_api_key_and_secret(api_key, api_secret),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_json(
                buy_order_created.model_copy(deep=True, update={"status": "FILLED"}).model_dump(
                    by_alias=True, mode="json"
                )
            )
        case _:
            raise ValueError(f"Unknown operating exchange: {operating_exchange}")


def _floor_round(value: float, *, ndigits: int) -> float:
    factor = 10**ndigits
    return math.floor(value * factor) / factor
