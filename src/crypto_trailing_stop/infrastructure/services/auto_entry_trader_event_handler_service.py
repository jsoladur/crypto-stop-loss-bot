import asyncio
import logging
import math
from datetime import UTC, datetime
from typing import Any, override

from aiogram import html
from pyee.asyncio import AsyncIOEventEmitter

from crypto_trailing_stop.commons.constants import (
    AUTO_ENTRY_MARKET_ORDER_SAFETY_FACTOR,
    AUTO_ENTRY_TRADER_MAX_ATTEMPS_TO_BUY,
    AUTO_ENTRY_TRADER_MINIMAL_AMOUNT_TO_INVEST,
    TRIGGER_BUY_ACTION_EVENT_NAME,
)
from crypto_trailing_stop.config.configuration_properties import ConfigurationProperties
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange import AbstractOperatingExchangeService
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums.order_side_enum import OrderSideEnum
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums.order_status_enum import (
    OrderStatusEnum,
)
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums.order_type_enum import OrderTypeEnum
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo.order import Order
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo.symbol_market_config import (
    SymbolMarketConfig,
)
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo.symbol_tickers import SymbolTickers
from crypto_trailing_stop.infrastructure.services.auto_buy_trader_config_service import AutoBuyTraderConfigService
from crypto_trailing_stop.infrastructure.services.base import AbstractEventHandlerService
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.enums.candlestick_enum import CandleStickEnum
from crypto_trailing_stop.infrastructure.services.enums.global_flag_enum import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.enums.push_notification_type_enum import PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.favourite_crypto_currency_service import (
    FavouriteCryptoCurrencyService,
)
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.orders_analytics_service import OrdersAnalyticsService
from crypto_trailing_stop.infrastructure.services.push_notification_service import PushNotificationService
from crypto_trailing_stop.infrastructure.services.stop_loss_percent_service import StopLossPercentService
from crypto_trailing_stop.infrastructure.services.vo.auto_buy_trader_config_item import AutoBuyTraderConfigItem
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.infrastructure.services.vo.crypto_market_metrics import CryptoMarketMetrics
from crypto_trailing_stop.infrastructure.services.vo.limit_sell_order_guard_metrics import LimitSellOrderGuardMetrics
from crypto_trailing_stop.infrastructure.services.vo.market_signal_item import MarketSignalItem
from crypto_trailing_stop.infrastructure.services.vo.stop_loss_percent_item import StopLossPercentItem
from crypto_trailing_stop.interfaces.telegram.services.telegram_service import TelegramService

logger = logging.getLogger(__name__)


class AutoEntryTraderEventHandlerService(AbstractEventHandlerService):
    def __init__(
        self,
        configuration_properties: ConfigurationProperties,
        event_emitter: AsyncIOEventEmitter,
        operating_exchange_service: AbstractOperatingExchangeService,
        push_notification_service: PushNotificationService,
        telegram_service: TelegramService,
        ccxt_remote_service: CcxtRemoteService,
        global_flag_service: GlobalFlagService,
        favourite_crypto_currency_service: FavouriteCryptoCurrencyService,
        buy_sell_signals_config_service: BuySellSignalsConfigService,
        auto_buy_trader_config_service: AutoBuyTraderConfigService,
        stop_loss_percent_service: StopLossPercentService,
        crypto_analytics_service: CryptoAnalyticsService,
        orders_analytics_service: OrdersAnalyticsService,
    ) -> None:
        super().__init__(operating_exchange_service, push_notification_service, telegram_service)
        self._configuration_properties = configuration_properties
        self._event_emitter = event_emitter
        self._ccxt_remote_service = ccxt_remote_service
        self._global_flag_service = global_flag_service
        self._favourite_crypto_currency_service = favourite_crypto_currency_service
        self._buy_sell_signals_config_service = buy_sell_signals_config_service
        self._auto_buy_trader_config_service = auto_buy_trader_config_service
        self._stop_loss_percent_service = stop_loss_percent_service
        self._crypto_analytics_service = crypto_analytics_service
        self._orders_analytics_service = orders_analytics_service
        self._lock = asyncio.Lock()

    @override
    def configure(self) -> None:
        self._event_emitter.add_listener(TRIGGER_BUY_ACTION_EVENT_NAME, self.on_buy_market_signal)

    async def trigger_immediate_buy_market_signal(self, symbol: str) -> None:
        crypto_market_metrics = await self._crypto_analytics_service.get_crypto_market_metrics(
            symbol, over_candlestick=CandleStickEnum.LAST
        )
        market_signal_item = MarketSignalItem(
            timestamp=datetime.now(UTC),
            symbol=crypto_market_metrics.symbol,
            timeframe="1h",
            signal_type="buy",
            rsi_state=crypto_market_metrics.rsi_state,
            atr=crypto_market_metrics.atr,
            closing_price=crypto_market_metrics.closing_price,
            ema_long_price=crypto_market_metrics.ema_long,
        )
        self._event_emitter.emit(TRIGGER_BUY_ACTION_EVENT_NAME, market_signal_item)

    async def on_buy_market_signal(self, market_signal_item: MarketSignalItem) -> None:
        async with self._lock:
            await self._internal_on_buy_market_signal(market_signal_item)

    async def _internal_on_buy_market_signal(self, market_signal_item: MarketSignalItem) -> None:
        try:
            is_enabled_for = await self._global_flag_service.is_enabled_for(GlobalFlagTypeEnum.AUTO_ENTRY_TRADER)
            if is_enabled_for:
                crypto_currency, fiat_currency = market_signal_item.symbol.split("/")
                buy_trader_config = await self._auto_buy_trader_config_service.find_by_symbol(crypto_currency)
                if buy_trader_config.fiat_wallet_percent_assigned > 0:
                    async with await self._operating_exchange_service.get_client() as client:
                        trading_market_config = (
                            await self._operating_exchange_service.get_trading_market_config_by_symbol(
                                market_signal_item.symbol, client=client
                            )
                        )
                        market_signal_item_atr_percent = market_signal_item.get_atr_percent(trading_market_config)
                        if (
                            market_signal_item_atr_percent
                            < self._configuration_properties.max_atr_percent_for_auto_entry
                        ):
                            await self._perform_trading(
                                market_signal_item,
                                crypto_currency,
                                fiat_currency,
                                buy_trader_config,
                                trading_market_config=trading_market_config,
                                client=client,
                            )
                        else:
                            reason_message = "    - 🎢 " + html.italic(
                                f"Current ATR ({market_signal_item_atr_percent}%) "
                                + f"exceeds the allowed risk threshold (&lt;={self._configuration_properties.max_atr_percent_for_auto_entry}%).\n"  # noqa: E501
                            )
                            reason_message += "⏸️ Trading paused to protect capital."
                            await self._notify_warning(market_signal_item, warning_reason_message=reason_message)
        except Exception as e:  # pragma: no cover
            logger.error(str(e), exc_info=True)
            await self._notify_fatal_error_via_telegram(e)

    async def _perform_trading(
        self,
        market_signal_item: MarketSignalItem,
        crypto_currency: str,
        fiat_currency: str,
        buy_trader_config: AutoBuyTraderConfigItem,
        *,
        trading_market_config: SymbolMarketConfig,
        client: Any,
    ) -> None:
        initial_amount_to_invest = await self._calculate_total_amount_to_invest(
            buy_trader_config, crypto_currency, fiat_currency, client=client
        )
        # XXX: [JMSOLA] Investing less than 25.0 EUR is not worthly
        if initial_amount_to_invest > AUTO_ENTRY_TRADER_MINIMAL_AMOUNT_TO_INVEST:
            await self._invest(
                market_signal_item,
                crypto_currency,
                fiat_currency,
                initial_amount_to_invest,
                trading_market_config=trading_market_config,
                client=client,
            )
        else:
            reason_message = "    - 💸 " + html.italic(
                f"Insufficient funds to invest ({initial_amount_to_invest:.2f} {fiat_currency}). "
                + f"Minimal funds needed are {AUTO_ENTRY_TRADER_MINIMAL_AMOUNT_TO_INVEST:.2f} {fiat_currency}"
            )
            await self._notify_warning(market_signal_item, warning_reason_message=reason_message)

    async def _invest(
        self,
        market_signal_item: MarketSignalItem,
        crypto_currency: str,
        fiat_currency: str,
        initial_amount_to_invest: float,
        *,
        trading_market_config: SymbolMarketConfig,
        client: Any,
    ) -> None:
        # XXX: [JMSOLA] Calculate buy order amount
        buy_sell_signals_config = await self._buy_sell_signals_config_service.find_by_symbol(crypto_currency)
        # Introduces a security buffer deposit (e.g. 99.5% of capital)
        amount_with_buffer = initial_amount_to_invest * AUTO_ENTRY_MARKET_ORDER_SAFETY_FACTOR
        new_buy_market_order, tickers = await self._execute_market_entry(
            market_signal_item,
            crypto_currency,
            fiat_currency,
            amount_with_buffer,
            trading_market_config=trading_market_config,
            client=client,
        )
        # XXX [JMSOLA]: Disabling temporary Limit Sell Guard order for precaution
        await self._global_flag_service.force_disable_by_name(GlobalFlagTypeEnum.LIMIT_SELL_ORDER_GUARD)
        try:
            # Creating new sell limite order
            new_limit_sell_order = await self._create_new_sell_limit_order(
                new_buy_market_order, trading_market_config, tickers, crypto_currency, client=client
            )
            guard_metrics = await self._update_stop_loss(
                new_limit_sell_order,
                trading_market_config,
                tickers,
                crypto_currency,
                buy_sell_signals_config,
                client=client,
            )
            # Ensure Auto-exit on sudden SELL 1H signal is enabled
            buy_sell_signals_config.enable_exit_on_sell_signal = True
            await self._buy_sell_signals_config_service.save_or_update(buy_sell_signals_config)
            # Notifying via Telegram
            await self._notify_success_alert(
                new_buy_market_order, new_limit_sell_order, tickers, guard_metrics, buy_sell_signals_config
            )
        finally:
            # Re-enable Limit Sell Order Guard, once stop loss is setup!
            await self._global_flag_service.toggle_by_name(GlobalFlagTypeEnum.LIMIT_SELL_ORDER_GUARD)

    async def _calculate_total_amount_to_invest(
        self, buy_trader_config: AutoBuyTraderConfigItem, crypto_currency: str, fiat_currency: str, client: Any
    ) -> float | int:
        fiat_wallet_assigned_decimal_value = buy_trader_config.fiat_wallet_percent_assigned / 100.0
        # 1.) Get total portfolio amount
        portfolio_balance = await self._operating_exchange_service.retrieve_porfolio_balance(
            fiat_currency, client=client
        )
        portfolio_assigned_amount = math.floor(portfolio_balance.total_balance * fiat_wallet_assigned_decimal_value)

        # XXX: [JMSOLA] Calculate already invested amount to not invest more the percent assigned in overall
        current_guard_metrics_list = await self._orders_analytics_service.calculate_all_limit_sell_order_guard_metrics(
            symbol=crypto_currency
        )
        already_invested_amount = math.ceil(
            sum(
                [
                    (guard_metrics.sell_order.amount * guard_metrics.avg_buy_price)
                    for guard_metrics in current_guard_metrics_list
                ]
            )
        )
        remaining_to_invest = portfolio_assigned_amount - already_invested_amount

        fiat_wallet_balance, *_ = await self._operating_exchange_service.get_trading_wallet_balances(
            symbols=fiat_currency.upper(), client=client
        )
        amount_to_invest = min(
            math.floor(fiat_wallet_balance.balance), math.floor(remaining_to_invest) if remaining_to_invest > 0 else 0
        )
        return amount_to_invest

    async def _execute_market_entry(
        self,
        market_signal_item: MarketSignalItem,
        crypto_currency: str,
        fiat_currency: str,
        amount_with_buffer: float,
        *,
        trading_market_config: SymbolMarketConfig,
        client: Any,
    ) -> tuple[Order, SymbolTickers]:
        new_buy_market_order: Order | None = None
        last_exception: Exception | None = None
        attemps = 1
        while new_buy_market_order is None and attemps <= AUTO_ENTRY_TRADER_MAX_ATTEMPS_TO_BUY:
            tickers = await self._operating_exchange_service.get_single_tickers_by_symbol(
                market_signal_item.symbol, client=client
            )
            try:
                # XXX: [JMSOLA] Get the current tickers.ask price for calculate the order_amount
                buy_order_amount = self._floor_round(
                    amount_with_buffer / tickers.ask_or_close, ndigits=trading_market_config.amount_precision
                )
                final_amount_to_invest = buy_order_amount * tickers.ask_or_close
                logger.info(
                    f"[Auto-Entry Trader][Attempt {attemps}] Trying to create BUY MARKET ORDER for {market_signal_item.symbol}, "  # noqa: E501
                    + f"which has current buy price {tickers.ask_or_close} {fiat_currency}. "
                    + f"Investing {final_amount_to_invest:.2f} {fiat_currency}, "
                    + f"buying {buy_order_amount} {crypto_currency}"
                )
                new_buy_market_order = await self._create_new_buy_market_order_and_wait_until_filled(
                    market_signal_item, buy_order_amount, client=client
                )
            except Exception as e:  # pragma: no cover
                last_exception = e
                logger.warning(
                    f"[Auto-Entry Trader][Attempt {attemps}] An error ocurred when creating the BUY MARKET ORDER for {market_signal_item.symbol}, "  # noqa: E501
                    + f"which had current buy price {tickers.ask_or_close} {fiat_currency} and "
                    + f"{buy_order_amount} {crypto_currency} as amount to invest. "
                    + f"Re-calculating buy order amount and trying again... :: {str(e)}"
                )
            finally:
                attemps += 1
        if new_buy_market_order is None and last_exception is not None:  # pragma: no cover
            raise last_exception
        return new_buy_market_order, tickers

    async def _create_new_buy_market_order_and_wait_until_filled(
        self, market_signal_item: MarketSignalItem, buy_order_amount: float | int, client: Any
    ) -> Order:
        new_buy_market_order: Order = await self._operating_exchange_service.create_order(
            order=Order(
                order_type=OrderTypeEnum.MARKET,
                side=OrderSideEnum.BUY,
                symbol=market_signal_item.symbol,
                amount=buy_order_amount,
            ),
            client=client,
        )
        while new_buy_market_order.status not in [OrderStatusEnum.FILLED, OrderStatusEnum.CANCELLED]:
            logger.info(
                f"[Auto-Entry Trader] NEW MARKET ORDER Id: '{new_buy_market_order.id}'. "
                + "Waiting 2 seconds to watch the new buy market order is already filled..."
            )
            await asyncio.sleep(delay=2.0)
            new_buy_market_order = await self._operating_exchange_service.get_order_by_id(
                new_buy_market_order.id, client=client
            )
        if new_buy_market_order.status == OrderStatusEnum.CANCELLED:
            raise ValueError("The recent BUY MARKET order was cancelled by the exchange!")
        return new_buy_market_order

    async def _create_new_sell_limit_order(
        self,
        new_buy_market_order: Order,
        trading_market_config: SymbolMarketConfig,
        tickers: SymbolTickers,
        crypto_currency: str,
        *,
        client: Any,
    ) -> Order:
        # # XXX [JMSOLA]: Once buy sell order is FILLED,
        # we are now creating a LIMIT SELL ORDER to pass
        # the responsibility to the Limit Sell Order Guard for selling,
        # at some further favorable point!
        crypto_currency_wallet, *_ = await self._operating_exchange_service.get_trading_wallet_balances(
            symbols=crypto_currency, client=client
        )
        new_limit_sell_order_amount = self._floor_round(
            min(crypto_currency_wallet.balance, new_buy_market_order.amount),
            ndigits=trading_market_config.amount_precision,
        )
        new_limit_sell_order = await self._operating_exchange_service.create_order(
            order=Order(
                order_type=OrderTypeEnum.LIMIT,
                side=OrderSideEnum.SELL,
                symbol=new_buy_market_order.symbol,
                price=self._floor_round(
                    # XXX: [JMSOLA] Price is unreachable in purpose,
                    # for giving to the Limit Sell Order Guard the chance to
                    # operate properly
                    tickers.close * 2,
                    ndigits=trading_market_config.price_precision,
                ),
                amount=new_limit_sell_order_amount,
            ),
            client=client,
        )
        return new_limit_sell_order

    async def _update_stop_loss(
        self,
        new_limit_sell_order: Order,
        trading_market_config: SymbolMarketConfig,
        tickers: SymbolTickers,
        crypto_currency: str,
        buy_sell_signals_config: BuySellSignalsConfigItem,
        *,
        client: Any,
    ) -> LimitSellOrderGuardMetrics:
        technical_indicators, *_ = await self._crypto_analytics_service.calculate_technical_indicators(
            new_limit_sell_order.symbol, client=client
        )
        last_candle_market_metrics = CryptoMarketMetrics.from_candlestick(
            new_limit_sell_order.symbol,
            candlestick=technical_indicators.iloc[CandleStickEnum.LAST],  # Last confirmed candle
            trading_market_config=trading_market_config,
        )
        avg_buy_price, *_ = await self._orders_analytics_service.calculate_correlated_avg_buy_price(
            new_limit_sell_order, trading_market_config=trading_market_config, client=client
        )
        suggested_stop_loss_percent_value = self._orders_analytics_service.calculate_suggested_stop_loss_percent_value(
            avg_buy_price,
            buy_sell_signals_config=buy_sell_signals_config,
            last_candle_market_metrics=last_candle_market_metrics,
            trading_market_config=trading_market_config,
        )
        # XXX [JMSOLA]: Calculate suggested stop loss and update it
        await self._stop_loss_percent_service.save_or_update(
            StopLossPercentItem(symbol=crypto_currency, value=suggested_stop_loss_percent_value)
        )
        guard_metrics, *_ = await self._orders_analytics_service.calculate_guard_metrics_by_sell_order(
            new_limit_sell_order, tickers=tickers, client=client
        )
        return guard_metrics

    async def _notify_warning(self, market_signal_item: MarketSignalItem, warning_reason_message: str) -> None:
        message = f"⚠️ {html.bold('AUTO-ENTRY TRADER WARNING')} ⚠️\n\n"
        message += f"Stopping trading operations for {market_signal_item.symbol}, despite recent BUY 1H signal.\n"  # noqa: E501
        message += "✴️ Reasons:\n"
        message += warning_reason_message
        await self._notify_alert_by_type(PushNotificationTypeEnum.AUTO_ENTRY_TRADER_ALERT, message)

    async def _notify_success_alert(
        self,
        new_buy_market_order: Order,
        new_limit_sell_order: Order,
        tickers: SymbolTickers,
        guard_metrics: LimitSellOrderGuardMetrics,
        buy_sell_signals_config: BuySellSignalsConfigItem,
    ) -> None:
        crypto_currency, fiat_currency = tickers.symbol.split("/")
        message = f"✅ {html.bold('MARKET BUY ORDER FILLED')} ✅\n\n"
        message += f"🔥 {new_buy_market_order.amount} {crypto_currency} purchased at {tickers.ask} {fiat_currency}"
        message += html.bold("\n\n⚠️ IMPORTANT CONSIDERATIONS ⚠️\n\n")
        new_limit_sell_order_price_formatted = f"{new_limit_sell_order.price} {fiat_currency}"
        message += (
            f"* 🚀 A new {html.bold(new_limit_sell_order.order_type.upper() + ' Sell Order')} ("
            + f"{new_limit_sell_order.amount} {crypto_currency}), "
            + f"further sell at {html.bold(new_limit_sell_order_price_formatted)}"
            + " has been CREATED to start looking at possible SELL ACTION 🤑\n"
        )
        message += f"* 🧊 {html.bold('Break-even Price')} = {guard_metrics.break_even_price} {fiat_currency}\n"
        message += f"* 🚏 {html.bold('Stop Loss')} updated to {guard_metrics.stop_loss_percent_value}%\n"
        message += f"* 🛡️ {html.bold('Safeguard Stop Price = ' + str(guard_metrics.suggested_safeguard_stop_price) + ' ' + fiat_currency)}\n"  # noqa: E501
        if buy_sell_signals_config.enable_exit_on_take_profit:
            message += (
                f"* 🎯 {html.bold('Take Profit Price')} = {guard_metrics.take_profit_limit_price} {fiat_currency}\n"  # noqa: E501
            )
        if buy_sell_signals_config.enable_exit_on_take_profit:
            message += f"* ⚡ {html.bold('Auto ATR Take-Profit Exit')} is ENABLED!\n"
            message += f"* 🟢 {html.bold('Potential Profit at TP')} = {html.code('+' + str(guard_metrics.potential_profit_at_tp) + ' ' + fiat_currency)}\n"  # noqa: E501
        else:
            message += (
                f"* ⚡ {html.bold('Auto ATR Take-Profit Exit')} is DISABLED! "
                + "Please, consider to enable it if needed!\n"
            )
        message += f"* 🔴 {html.bold('Potential Loss at SL')} = {html.code('-' + str(guard_metrics.potential_loss_at_sl) + ' ' + fiat_currency)}"  # noqa: E501
        await self._notify_alert_by_type(PushNotificationTypeEnum.AUTO_ENTRY_TRADER_ALERT, message)

    def _floor_round(self, value: float, *, ndigits: int) -> float:
        factor = 10**ndigits
        return math.floor(value * factor) / factor
