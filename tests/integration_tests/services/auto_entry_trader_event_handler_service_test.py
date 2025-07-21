import asyncio
import logging
import math
from datetime import UTC, datetime
from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from aiogram import Bot
from faker import Faker
from pydantic import RootModel
from pytest_httpserver import HTTPServer
from pytest_httpserver.httpserver import HandlerType

from crypto_trailing_stop.commons.constants import (
    BIT2ME_TAKER_FEES,
    DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE,
    NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL,
    TRIGGER_BUY_ACTION_EVENT_NAME,
)
from crypto_trailing_stop.config import get_event_emitter
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_pagination_result_dto import Bit2MePaginationResultDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_porfolio_balance_dto import (
    Bit2MePortfolioBalanceDto,
    ConvertedBalanceDto,
    TotalDto,
)
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_trade_dto import Bit2MeTradeDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_trading_wallet_balance import (
    Bit2MeTradingWalletBalanceDto,
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
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.infrastructure.services.vo.market_signal_item import MarketSignalItem
from tests.helpers.background_jobs_test_utils import disable_all_background_jobs_except
from tests.helpers.enums import AutoEntryTraderWarningTypeEnum
from tests.helpers.httpserver_pytest import Bit2MeAPIQueryMatcher, Bit2MeAPIRequestMacher
from tests.helpers.object_mothers import (
    Bit2MeOrderDtoObjectMother,
    Bit2MeTickersDtoObjectMother,
    Bit2MeTradeDtoObjectMother,
    Bit2MeTradingWalletBalanceDtoObjectMother,
)
from tests.helpers.ohlcv_test_utils import get_fetch_ohlcv_random_result
from tests.helpers.sell_orders_test_utils import generate_trades

logger = logging.getLogger(__name__)

use_cases = [(boolean, warning_type) for boolean in [False, True] for warning_type in AutoEntryTraderWarningTypeEnum]
use_cases = [(boolean, warning_type, bool(idx % 2)) for idx, (boolean, warning_type) in enumerate(use_cases)]


@pytest.mark.parametrize("use_event_emitter,warning_type,enable_atr_auto_take_profit", use_cases)
@pytest.mark.asyncio
async def should_create_market_buy_order_and_limit_sell_when_market_buy_1h_signal_is_triggered(
    faker: Faker,
    use_event_emitter: bool,
    warning_type: AutoEntryTraderWarningTypeEnum,
    enable_atr_auto_take_profit: bool,
    integration_test_env: tuple[HTTPServer, str],
) -> None:
    """
    Test that all expected calls to Bit2Me are made when a limit sell order has to be filled
    """
    # Mock the Bit2Me API
    _, httpserver, bit2me_api_key, bit2me_api_secret, *_ = integration_test_env

    # Disable all jobs by default for test purposes!
    await disable_all_background_jobs_except(exclusion=[GlobalFlagTypeEnum.AUTO_ENTRY_TRADER])

    auto_entry_trader_event_handler_service = AutoEntryTraderEventHandlerService()
    auto_buy_trader_config_service = AutoBuyTraderConfigService()
    buy_sell_signals_config_service = BuySellSignalsConfigService()
    global_flag_service = GlobalFlagService()

    market_signal_item, _, crypto_currency, *_ = _prepare_httpserver_mock(
        faker, httpserver, bit2me_api_key, bit2me_api_secret, warning_type=warning_type
    )
    if not enable_atr_auto_take_profit:
        await buy_sell_signals_config_service.save_or_update(
            BuySellSignalsConfigItem(symbol=crypto_currency, auto_exit_atr_take_profit=False)
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
                if use_event_emitter:
                    event_emitter = get_event_emitter()
                    event_emitter.emit(TRIGGER_BUY_ACTION_EVENT_NAME, market_signal_item)
                    await asyncio.sleep(delay=15.0)
                else:
                    await auto_entry_trader_event_handler_service.on_buy_market_signal(market_signal_item)

            httpserver.check_assertions()
            notify_fatal_error_via_telegram_mock.assert_not_called()
            if warning_type == AutoEntryTraderWarningTypeEnum.NONE:
                toggle_task_mock.assert_called()

                is_enabled_for_limit_sell_order_guard = await global_flag_service.is_enabled_for(
                    GlobalFlagTypeEnum.LIMIT_SELL_ORDER_GUARD
                )
                assert is_enabled_for_limit_sell_order_guard is True

                buy_sell_signals_config = await buy_sell_signals_config_service.find_by_symbol(crypto_currency)
                assert buy_sell_signals_config.auto_exit_sell_1h is True
            else:
                toggle_task_mock.assert_not_called()


def _prepare_httpserver_mock(
    faker: Faker,
    httpserver: HTTPServer,
    bit2me_api_key: str,
    bik2me_api_secret: str,
    *,
    warning_type: AutoEntryTraderWarningTypeEnum,
) -> tuple[str, str, str]:
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
        handler_type=HandlerType.PERMANENT,
    ).respond_with_json(fetch_ohlcv_return_value)

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
    if warning_type != AutoEntryTraderWarningTypeEnum.ATR_TOO_HIGH:
        global_portfolio_balance = faker.pyfloat(min_value=2_500, max_value=2_700)
        bit2me_pro_balance = (
            faker.pyfloat(min_value=1, max_value=20)
            if warning_type == AutoEntryTraderWarningTypeEnum.NOT_ENOUGH_FUNDS
            else (global_portfolio_balance * 0.9)
        )
        # Global portfolio
        httpserver.expect(
            Bit2MeAPIRequestMacher(
                "/bit2me-api/v1/portfolio/balance",
                query_string=urlencode({"userCurrency": fiat_currency.upper()}, doseq=False),
                method="GET",
            ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
            handler_type=HandlerType.ONESHOT,
        ).respond_with_json(
            RootModel[list[Bit2MePortfolioBalanceDto]](
                [
                    Bit2MePortfolioBalanceDto(
                        serviceName="all",
                        total=TotalDto(
                            converted_balance=ConvertedBalanceDto(currency="EUR", value=global_portfolio_balance)
                        ),
                        wallets=[],
                    )
                ]
            ).model_dump(mode="json", by_alias=True)
        )

        # Mock tickers
        tickers = Bit2MeTickersDtoObjectMother.create(symbol=symbol, close=closing_price * 1.02)
        # Simulate previous orders
        previous_order_avg_buy_price = closing_price * 0.85
        opened_sell_bit2me_orders = [
            Bit2MeOrderDtoObjectMother.create(
                created_at=faker.past_datetime(tzinfo=UTC),
                side="sell",
                symbol=symbol,
                order_type="limit",
                order_amount=_floor_round(
                    (bit2me_pro_balance * 0.01) / previous_order_avg_buy_price,
                    ndigits=NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(
                        market_signal_item.symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE
                    ),
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
                    (bit2me_pro_balance * 0.02) / previous_order_avg_buy_price,
                    ndigits=NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(
                        market_signal_item.symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE
                    ),
                ),
                price=(closing_price * 0.92) * 2,
                status=faker.random_element(["open", "inactive"]),
            ),
        ]
        # Mock call to /v1/trading/order to get opened sell orders
        httpserver.expect(
            Bit2MeAPIRequestMacher(
                "/bit2me-api/v1/trading/order",
                method="GET",
                query_string=urlencode(
                    {"direction": "desc", "status_in": "open,inactive", "side": "sell"}, doseq=False
                ),
            ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
            handler_type=HandlerType.ONESHOT,
        ).respond_with_json(
            RootModel[list[Bit2MeOrderDto]](opened_sell_bit2me_orders).model_dump(mode="json", by_alias=True)
        )

        buy_trades = generate_trades(faker, opened_sell_bit2me_orders, number_of_trades=1)
        for _ in range(len(opened_sell_bit2me_orders)):
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

        eur_wallet_balance = Bit2MeTradingWalletBalanceDtoObjectMother.create(
            currency=fiat_currency, balance=round(bit2me_pro_balance, ndigits=2)
        )
        # Trading Wallet Balance for FIAT currency
        httpserver.expect(
            Bit2MeAPIRequestMacher(
                "/bit2me-api/v1/trading/wallet/balance",
                query_string=urlencode({"symbols": fiat_currency.upper()}, doseq=False),
                method="GET",
            ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
            handler_type=HandlerType.ONESHOT,
        ).respond_with_json(
            RootModel[list[Bit2MeTradingWalletBalanceDto]]([eur_wallet_balance]).model_dump(mode="json", by_alias=True)
        )
        if warning_type != AutoEntryTraderWarningTypeEnum.NOT_ENOUGH_FUNDS:
            httpserver.expect(
                Bit2MeAPIRequestMacher(
                    "/bit2me-api/v2/trading/tickers", method="GET", query_string={"symbol": symbol}
                ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_json(RootModel[list[Bit2MeTickersDto]]([tickers]).model_dump(mode="json", by_alias=True))

            # Mock call to POST /v1/trading/order
            buy_order_amount = _floor_round(
                bit2me_pro_balance / tickers.close,
                ndigits=NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(
                    market_signal_item.symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE
                ),
            )
            buy_order_created = Bit2MeOrderDtoObjectMother.create(
                symbol=symbol, side="buy", order_amount=buy_order_amount, order_type="market", status="open"
            )
            httpserver.expect(
                Bit2MeAPIRequestMacher("/bit2me-api/v1/trading/order", method="POST").set_bit2me_api_key_and_secret(
                    bit2me_api_key, bik2me_api_secret
                ),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_json(buy_order_created.model_dump(by_alias=True, mode="json"))
            # Simulating waiting for FILLED
            for _ in range(faker.pyint(min_value=1, max_value=3)):
                httpserver.expect(
                    Bit2MeAPIRequestMacher(
                        f"/bit2me-api/v1/trading/order/{buy_order_created.id}", method="GET"
                    ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
                    handler_type=HandlerType.ONESHOT,
                ).respond_with_json(buy_order_created.model_dump(by_alias=True, mode="json"))
            # Already filled!
            httpserver.expect(
                Bit2MeAPIRequestMacher(
                    f"/bit2me-api/v1/trading/order/{buy_order_created.id}", method="GET"
                ).set_bit2me_api_key_and_secret(bit2me_api_key, bik2me_api_secret),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_json(
                buy_order_created.model_copy(deep=True, update={"status": "filled"}).model_dump(
                    by_alias=True, mode="json"
                )
            )
            # Trading Wallet Balance for CRYPTO currency
            buy_order_amount_after_feeds = buy_order_amount * (1 - BIT2ME_TAKER_FEES)
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
                            currency=crypto_currency, balance=round(buy_order_amount_after_feeds, ndigits=2)
                        )
                    ]
                ).model_dump(mode="json", by_alias=True)
            )
            # Mock Limit Sell order created
            httpserver.expect(
                Bit2MeAPIRequestMacher("/bit2me-api/v1/trading/order", method="POST").set_bit2me_api_key_and_secret(
                    bit2me_api_key, bik2me_api_secret
                ),
                handler_type=HandlerType.ONESHOT,
            ).respond_with_json(
                Bit2MeOrderDtoObjectMother.create(
                    symbol=symbol,
                    side="sell",
                    order_amount=buy_order_amount_after_feeds,
                    order_type="limit",
                    status="open",
                    price=tickers.close * 2,
                ).model_dump(by_alias=True, mode="json")
            )
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
                    data=[
                        Bit2MeTradeDtoObjectMother.create(
                            side="buy",
                            symbol=market_signal_item.symbol,
                            price=tickers.close,
                            amount=buy_order_amount_after_feeds,
                        )
                    ],
                    total=faker.pyint(min_value=50, max_value=100),
                ).model_dump(mode="json", by_alias=True)
            )

    return market_signal_item, symbol, crypto_currency, fiat_currency


def _floor_round(value: float, *, ndigits: int) -> float:
    factor = 10**ndigits
    return math.floor(value * factor) / factor
