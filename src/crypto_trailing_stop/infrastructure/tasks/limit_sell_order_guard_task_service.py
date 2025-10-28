import logging
from datetime import UTC, datetime
from typing import override

from aiogram import html
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from httpx import AsyncClient

from crypto_trailing_stop.commons.constants import (
    INITIAL_LIMIT_SELL_ORDER_GUARD_SAFETY_FACTOR,
    LIMIT_SELL_ORDER_GUARD_SAFETY_FACTOR_STEP,
)
from crypto_trailing_stop.config.configuration_properties import ConfigurationProperties
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange import AbstractOperatingExchangeService
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums.order_side_enum import OrderSideEnum
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums.order_type_enum import OrderTypeEnum
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo.order import Order
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo.symbol_market_config import (
    SymbolMarketConfig,
)
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo.symbol_tickers import SymbolTickers
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo.trade import Trade
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum, PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.enums.candlestick_enum import CandleStickEnum
from crypto_trailing_stop.infrastructure.services.favourite_crypto_currency_service import (
    FavouriteCryptoCurrencyService,
)
from crypto_trailing_stop.infrastructure.services.limit_sell_order_guard_cache_service import (
    LimitSellOrderGuardCacheService,
)
from crypto_trailing_stop.infrastructure.services.market_signal_service import MarketSignalService
from crypto_trailing_stop.infrastructure.services.orders_analytics_service import OrdersAnalyticsService
from crypto_trailing_stop.infrastructure.services.push_notification_service import PushNotificationService
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.infrastructure.services.vo.crypto_market_metrics import CryptoMarketMetrics
from crypto_trailing_stop.infrastructure.services.vo.limit_sell_order_guard_metrics import LimitSellOrderGuardMetrics
from crypto_trailing_stop.infrastructure.tasks.base import AbstractTaskService
from crypto_trailing_stop.infrastructure.tasks.vo.auto_exit_reason import AutoExitReason
from crypto_trailing_stop.infrastructure.tasks.vo.technical_indicators_cache_item import TechnicalIndicatorsCacheItem
from crypto_trailing_stop.interfaces.telegram.services.telegram_service import TelegramService

logger = logging.getLogger(__name__)


class LimitSellOrderGuardTaskService(AbstractTaskService):
    def __init__(
        self,
        configuration_properties: ConfigurationProperties,
        operating_exchange_service: AbstractOperatingExchangeService,
        push_notification_service: PushNotificationService,
        telegram_service: TelegramService,
        scheduler: AsyncIOScheduler,
        market_signal_service: MarketSignalService,
        ccxt_remote_service: CcxtRemoteService,
        limit_sell_order_guard_cache_service: LimitSellOrderGuardCacheService,
        favourite_crypto_currency_service: FavouriteCryptoCurrencyService,
        buy_sell_signals_config_service: BuySellSignalsConfigService,
        crypto_analytics_service: CryptoAnalyticsService,
        orders_analytics_service: OrdersAnalyticsService,
    ):
        super().__init__(operating_exchange_service, push_notification_service, telegram_service, scheduler)
        self._configuration_properties = configuration_properties
        self._market_signal_service = market_signal_service
        self._ccxt_remote_service = ccxt_remote_service
        self._limit_sell_order_guard_cache_service = limit_sell_order_guard_cache_service
        self._favourite_crypto_currency_service = favourite_crypto_currency_service
        self._buy_sell_signals_config_service = buy_sell_signals_config_service
        self._crypto_analytics_service = crypto_analytics_service
        self._orders_analytics_service = orders_analytics_service
        self._exchange = self._ccxt_remote_service.get_exchange()
        self._technical_indicators_by_symbol_cache: dict[str, TechnicalIndicatorsCacheItem] = {}

    @override
    def get_global_flag_type(self) -> GlobalFlagTypeEnum:
        return GlobalFlagTypeEnum.LIMIT_SELL_ORDER_GUARD

    @override
    async def _run(self) -> None:
        async with await self._operating_exchange_service.get_client() as client:
            sell_orders = await self._operating_exchange_service.get_pending_sell_orders(client=client)
            if sell_orders:
                await self._handle_opened_sell_orders(sell_orders, client=client)
            else:  # pragma: no cover
                logger.info("There are no opened limit sell orders to handle! Let's see in the upcoming executions...")

    @override
    def _get_job_trigger(self) -> IntervalTrigger:
        return IntervalTrigger(seconds=self._configuration_properties.job_interval_seconds)

    async def _handle_opened_sell_orders(self, opened_sell_orders: list[Order], *, client: AsyncClient) -> None:
        # Refresh technical indicators if needed
        await self._refresh_technical_indicators_by_symbol_cache_if_needed(opened_sell_orders, client=client)
        # Get current tickers for getting closing prices
        current_tickers_by_symbol: dict[str, SymbolTickers] = await self._fetch_tickers_for_open_sell_orders(
            opened_sell_orders, client=client
        )
        last_buy_trades_by_symbol: dict[str, Trade] = await self._get_last_buy_trades_by_opened_sell_orders(
            opened_sell_orders, client=client
        )
        previous_used_buy_trades: dict[str, float] = {}
        for sell_order in opened_sell_orders:
            try:
                previous_used_buy_trades, *_ = await self._handle_single_sell_order(
                    sell_order,
                    tickers=current_tickers_by_symbol[sell_order.symbol],
                    last_buy_trades=last_buy_trades_by_symbol[sell_order.symbol],
                    previous_used_buy_trades=previous_used_buy_trades,
                    client=client,
                )
            except Exception as e:  # pragma: no cover
                logger.error(str(e), exc_info=True)
                await self._notify_fatal_error_via_telegram(e)

    async def _handle_single_sell_order(
        self,
        sell_order: Order,
        *,
        tickers: SymbolTickers,
        last_buy_trades: list[Trade],
        previous_used_buy_trades: dict[str, float],
        client: AsyncClient,
    ) -> set[str]:
        crypto_currency, fiat_currency = sell_order.symbol.split("/")
        buy_sell_signals_config = await self._buy_sell_signals_config_service.find_by_symbol(crypto_currency)
        trading_market_config = await self._operating_exchange_service.get_trading_market_config_by_symbol(
            sell_order.symbol, client=client
        )
        technical_indicators = self._technical_indicators_by_symbol_cache[sell_order.symbol].technical_indicators
        prev_candle_market_metrics = CryptoMarketMetrics.from_candlestick(
            sell_order.symbol,
            candlestick=technical_indicators.iloc[CandleStickEnum.PREV],
            trading_market_config=trading_market_config,
        )
        last_candle_market_metrics = CryptoMarketMetrics.from_candlestick(
            sell_order.symbol,
            candlestick=technical_indicators.iloc[CandleStickEnum.LAST],
            trading_market_config=trading_market_config,
        )
        (
            guard_metrics,
            previous_used_buy_trades,
        ) = await self._orders_analytics_service.calculate_guard_metrics_by_sell_order(
            sell_order,
            tickers=tickers,
            buy_sell_signals_config=buy_sell_signals_config,
            technical_indicators=technical_indicators,
            last_buy_trades=last_buy_trades,
            previous_used_buy_trades=previous_used_buy_trades,
            client=client,
        )
        tickers_close_formatted = round(tickers.close, ndigits=trading_market_config.price_precision)
        logger.info(
            f"Supervising {sell_order.order_type.upper()} SELL order {repr(sell_order)} :: "
            + f"Avg Buy Price = {guard_metrics.avg_buy_price} {fiat_currency} / "
            + f"Break-Even Price = {guard_metrics.break_even_price} {fiat_currency} / "
            + f"Stop Loss = {guard_metrics.stop_loss_percent_value}% / "
            + f"Stop Price = {guard_metrics.safeguard_stop_price} {fiat_currency} / "
            + f"ATR Take Profit Limit price = {guard_metrics.suggested_take_profit_limit_price} {fiat_currency} / "
            + f"ATR value = {guard_metrics.current_attr_value} {fiat_currency} / "
            + f"Current Price = {tickers_close_formatted} {fiat_currency}"
        )
        auto_exit_reason = await self._is_moment_to_exit(
            sell_order=sell_order,
            tickers=tickers,
            buy_sell_signals_config=buy_sell_signals_config,
            guard_metrics=guard_metrics,
            prev_candle_market_metrics=prev_candle_market_metrics,
            last_candle_market_metrics=last_candle_market_metrics,
        )
        if auto_exit_reason.is_exit:
            new_sell_market_order = await self._execute_market_exit(
                sell_order=sell_order,
                tickers=tickers,
                crypto_currency=crypto_currency,
                trading_market_config=trading_market_config,
                auto_exit_reason=auto_exit_reason,
                client=client,
            )
            await self._notify_new_market_sell_order_created_via_telegram(
                new_sell_market_order,
                tickers=tickers,
                last_candle_market_metrics=last_candle_market_metrics,
                guard_metrics=guard_metrics,
                auto_exit_reason=auto_exit_reason,
            )
        return (previous_used_buy_trades,)

    async def _is_moment_to_exit(
        self,
        *,
        sell_order: Order,
        tickers: SymbolTickers,
        buy_sell_signals_config: BuySellSignalsConfigItem,
        guard_metrics: LimitSellOrderGuardMetrics,
        prev_candle_market_metrics: CryptoMarketMetrics,
        last_candle_market_metrics: CryptoMarketMetrics,
    ) -> AutoExitReason:
        """Determines if it's the right moment to exit the sell order based on various conditions."""
        # Check if the sell order is marked for immediate sell
        immediate_sell_order_item = self._limit_sell_order_guard_cache_service.pop_immediate_sell_order(sell_order.id)
        # Initialize variables
        is_marked_for_immediate_sell = immediate_sell_order_item is not None
        percent_to_sell = immediate_sell_order_item.percent_to_sell if is_marked_for_immediate_sell else 100.0
        stop_loss_triggered, take_profit_reached, exit_on_sell_signal, exit_on_bearish_divergence = (
            False,
            False,
            False,
            False,
        )
        if not is_marked_for_immediate_sell:
            # Check if the safeguard stop price is reached
            stop_loss_triggered = self._is_stop_loss_triggered(tickers=tickers, guard_metrics=guard_metrics)
            if not stop_loss_triggered:
                # Calculate exit_on_sell_signal
                (
                    exit_on_sell_signal,
                    exit_on_bearish_divergence,
                ) = await self._should_auto_exit_on_sell_or_bearish_divergence_1h_signal(
                    sell_order=sell_order,
                    tickers=tickers,
                    guard_metrics=guard_metrics,
                    buy_sell_signals_config=buy_sell_signals_config,
                    prev_candle_market_metrics=prev_candle_market_metrics,
                    last_candle_market_metrics=last_candle_market_metrics,
                )
                if not exit_on_sell_signal and not exit_on_bearish_divergence:
                    take_profit_reached = await self._should_auto_exit_on_take_profit_reached(
                        tickers=tickers, guard_metrics=guard_metrics, buy_sell_signals_config=buy_sell_signals_config
                    )
        return AutoExitReason(
            is_marked_for_immediate_sell=is_marked_for_immediate_sell,
            stop_loss_triggered=stop_loss_triggered,
            exit_on_bearish_divergence=exit_on_bearish_divergence,
            exit_on_sell_signal=exit_on_sell_signal,
            take_profit_reached=take_profit_reached,
            percent_to_sell=percent_to_sell,
        )

    async def _execute_market_exit(
        self,
        *,
        sell_order: Order,
        tickers: SymbolTickers,
        crypto_currency: str,
        trading_market_config: SymbolMarketConfig,
        auto_exit_reason: AutoExitReason,
        client,
    ) -> Order:
        final_amount_to_sell = self._get_final_amount_to_sell(sell_order, trading_market_config, auto_exit_reason)
        # Cancel current take-profit sell limit order
        await self._operating_exchange_service.cancel_order(sell_order, client=client)
        # Create new market SELL order
        new_sell_market_order = await self._ensure_market_sell_order_creation(
            sell_order=sell_order,
            trading_market_config=trading_market_config,
            final_amount_to_sell=final_amount_to_sell,
            client=client,
        )
        logger.info(
            f"[LIMIT SELL ORDER GUARD] NEW MARKET ORDER Id: '{new_sell_market_order.id}', "
            + f"for selling {auto_exit_reason.percent_to_sell}% "
            + f"of {sell_order.amount} {crypto_currency} immediately!"  # noqa: E501
        )
        if (remaining_amount := sell_order.amount - final_amount_to_sell) > 0:
            # NOTE: If we sold a percent less than 100.0%,
            #  we have to create again the sell order with the remaining order amount
            await self._create_sell_order_for_remaining_amount(
                sell_order=sell_order,
                tickers=tickers,
                crypto_currency=crypto_currency,
                trading_market_config=trading_market_config,
                remaining_amount=remaining_amount,
                client=client,
            )
        return new_sell_market_order

    async def _ensure_market_sell_order_creation(
        self,
        *,
        sell_order: Order,
        trading_market_config: SymbolMarketConfig,
        final_amount_to_sell: float,
        client: AsyncClient,
    ):
        new_sell_market_order: Order | None = None
        last_exception: Exception | None = None
        current_limit_sell_order_guard_safety_factor = INITIAL_LIMIT_SELL_ORDER_GUARD_SAFETY_FACTOR
        while new_sell_market_order is None and current_limit_sell_order_guard_safety_factor < 1:
            try:
                tickers = await self._operating_exchange_service.get_single_tickers_by_symbol(
                    sell_order.symbol, client=client
                )
                new_sell_market_order = await self._operating_exchange_service.create_order(
                    order=Order(
                        order_type=OrderTypeEnum.LIMIT,
                        side=sell_order.side,
                        symbol=sell_order.symbol,
                        price=self._floor_round(
                            # XXX: [JMSOLA] Limit Sell order will be immediately filled
                            # since the price is less than the current bid/close one.
                            tickers.bid_or_close * current_limit_sell_order_guard_safety_factor,
                            ndigits=trading_market_config.price_precision,
                        ),
                        amount=final_amount_to_sell,
                    ),
                    client=client,
                )
            except Exception as e:  # pragma: no cover
                last_exception = e
            finally:
                current_limit_sell_order_guard_safety_factor += LIMIT_SELL_ORDER_GUARD_SAFETY_FACTOR_STEP

        if new_sell_market_order is None and last_exception is not None:  # pragma: no cover
            raise last_exception
        return new_sell_market_order

    def _is_stop_loss_triggered(
        self, *, tickers: SymbolTickers, guard_metrics: LimitSellOrderGuardMetrics
    ) -> tuple[bool, bool, bool]:
        # XXX: [JMSOLA] Check if the safeguard stop price is reached
        # or the current sell price (bid) is below the safeguard stop price
        stop_loss_triggered = bool(tickers.bid_or_close < guard_metrics.safeguard_stop_price)
        return stop_loss_triggered

    async def _should_auto_exit_on_sell_or_bearish_divergence_1h_signal(
        self,
        *,
        sell_order: Order,
        tickers: SymbolTickers,
        guard_metrics: LimitSellOrderGuardMetrics,
        buy_sell_signals_config: BuySellSignalsConfigItem,
        prev_candle_market_metrics: CryptoMarketMetrics,
        last_candle_market_metrics: CryptoMarketMetrics,
    ) -> tuple[bool, bool]:
        exit_on_sell_signal, exit_on_bearish_divergence = False, False
        if (
            buy_sell_signals_config.enable_exit_on_sell_signal
            or buy_sell_signals_config.enable_exit_on_divergence_signal
        ):
            last_market_1h_signal = await self._market_signal_service.find_last_market_signal(sell_order.symbol)
            if (
                last_market_1h_signal is not None
                and last_market_1h_signal.timestamp > sell_order.created_at
                and tickers.bid_or_close >= guard_metrics.break_even_price
            ):  # Use bid for break-even check
                exit_on_sell_signal = bool(
                    buy_sell_signals_config.enable_exit_on_sell_signal
                    and last_market_1h_signal.signal_type == "sell"
                    and last_candle_market_metrics.macd_hist < 0
                    and last_candle_market_metrics.macd_hist < prev_candle_market_metrics.macd_hist
                )
                exit_on_bearish_divergence = bool(
                    buy_sell_signals_config.enable_exit_on_divergence_signal
                    and last_market_1h_signal.signal_type == "bearish_divergence"
                )
        return exit_on_sell_signal, exit_on_bearish_divergence

    async def _should_auto_exit_on_take_profit_reached(
        self,
        *,
        tickers: SymbolTickers,
        guard_metrics: LimitSellOrderGuardMetrics,
        buy_sell_signals_config: BuySellSignalsConfigItem,
    ) -> bool:
        take_profit_reached = False
        if buy_sell_signals_config.enable_exit_on_take_profit:
            # Ensuring we are not selling below the break even price,
            # regardless what the ATR Take profit limit price is!
            take_profit_reached = bool(
                tickers.bid_or_close >= guard_metrics.break_even_price  # Use bid
                and tickers.bid_or_close >= guard_metrics.suggested_take_profit_limit_price  # Use bid
            )
        return take_profit_reached

    async def _create_sell_order_for_remaining_amount(
        self,
        *,
        sell_order: Order,
        tickers: SymbolTickers,
        crypto_currency: str,
        trading_market_config: SymbolMarketConfig,
        remaining_amount: float,
        client: AsyncClient,
    ) -> None:
        crypto_currency_wallet, *_ = await self._operating_exchange_service.get_trading_wallet_balances(
            symbols=crypto_currency, client=client
        )
        new_limit_sell_order_amount = self._floor_round(
            min(crypto_currency_wallet.balance, remaining_amount), ndigits=trading_market_config.amount_precision
        )
        new_limit_sell_order = await self._operating_exchange_service.create_order(
            order=Order(
                order_type=OrderTypeEnum.LIMIT,
                side=OrderSideEnum.SELL,
                symbol=sell_order.symbol,
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
        logger.info(
            f"[LIMIT SELL ORDER GUARD] NEW LIMIT SELL ORDER Id: '{new_limit_sell_order.id}', "
            + f"for selling continue monitoring the remaining {remaining_amount} {crypto_currency}!"
        )

    async def _notify_new_market_sell_order_created_via_telegram(
        self,
        new_sell_market_order: Order,
        *,
        tickers: SymbolTickers,
        last_candle_market_metrics: SymbolTickers,
        guard_metrics: LimitSellOrderGuardMetrics,
        auto_exit_reason: AutoExitReason,
    ) -> None:
        crypto_currency, fiat_currency = new_sell_market_order.symbol.split("/")
        amount_message = f"{new_sell_market_order.amount} {crypto_currency}"
        buy_price_message = f"{guard_metrics.avg_buy_price} {fiat_currency}"
        net_revenue_message = f"{guard_metrics.net_revenue} {fiat_currency}"

        title_icon = "🚨" if guard_metrics.net_revenue < 0 else "🟢"
        reason_icon = "💥" if guard_metrics.net_revenue < 0 else "✳️"
        text_message = f"{title_icon} {html.bold('MARKET SELL ORDER FILLED')} {title_icon}\n\n"
        text_message += f"{html.bold(amount_message)} {html.bold('HAS BEEN SOLD')} 💰\n"  # noqa: E501
        text_message += f"💳 Buy Price: {html.code(buy_price_message)}\n"
        text_message += f"🏦 Net Revenue: {html.code(net_revenue_message)}\n\n"
        text_message += f"{reason_icon} Reason:\n"
        details = self._get_notification_message_details(
            tickers, last_candle_market_metrics, guard_metrics, auto_exit_reason, crypto_currency, fiat_currency
        )
        text_message += f"- {details}\n"
        await self._notify_alert_by_type(
            PushNotificationTypeEnum.LIMIT_SELL_ORDER_GUARD_EXECUTED_ALERT, message=text_message
        )

    def _get_notification_message_details(
        self,
        tickers: SymbolTickers,
        last_candle_market_metrics: CryptoMarketMetrics,
        guard_metrics: LimitSellOrderGuardMetrics,
        auto_exit_reason: AutoExitReason,
        crypto_currency: str,
        fiat_currency: str,
    ) -> str:
        current_price_message = f"{tickers.bid_or_close} {fiat_currency}"
        if auto_exit_reason.is_marked_for_immediate_sell:
            details = (
                "Order was marked for immediate sell. Executing market order immediately at "
                + f"current {crypto_currency} price ({html.code(current_price_message)})."
            )
        elif auto_exit_reason.stop_loss_triggered:
            safeguard_stop_price_message = f"{guard_metrics.safeguard_stop_price} {fiat_currency}"
            price_message = f"Current {crypto_currency} price ({html.code(current_price_message)})"
            stop_price_message = f"safeguard stop price calculated ({html.code(safeguard_stop_price_message)})"
            details = f"{price_message} is lower than the {stop_price_message}."
        elif auto_exit_reason.exit_on_bearish_divergence:
            details = (
                f"At current {crypto_currency} price ({html.code(current_price_message)}), "
                + "a BEARISH DIVERGENCE signal has suddenly appeared."
            )
        elif auto_exit_reason.exit_on_sell_signal:
            details = (
                f"At current {crypto_currency} price ({html.code(current_price_message)}), "
                + "a SELL 1H signal has suddenly appeared."
            )
        elif auto_exit_reason.take_profit_reached:
            suggested_take_profit_limit_price_message = (
                f"{guard_metrics.suggested_take_profit_limit_price} {fiat_currency}"
            )
            details = (
                f"Current {crypto_currency} price ({html.code(current_price_message)}) "
                + f"is higher than the ATR-based take profit calculated ({html.code(suggested_take_profit_limit_price_message)})."  # noqa: E501
            )
        return details

    async def _refresh_technical_indicators_by_symbol_cache_if_needed(
        self, opened_sell_orders: list[Order], *, client: AsyncClient
    ) -> None:
        now = datetime.now(UTC)
        open_sell_order_symbols = set([open_sell_order.symbol for open_sell_order in opened_sell_orders])
        async with self._exchange as exchange:
            for symbol in open_sell_order_symbols:
                if (
                    symbol not in self._technical_indicators_by_symbol_cache
                    or self._technical_indicators_by_symbol_cache[symbol].next_update_datetime < now
                ):
                    technical_indicators, *_ = await self._crypto_analytics_service.calculate_technical_indicators(
                        symbol, client=client, exchange=exchange
                    )
                    self._technical_indicators_by_symbol_cache[symbol] = TechnicalIndicatorsCacheItem(
                        technical_indicators=technical_indicators
                    )

    def _get_final_amount_to_sell(
        self, sell_order: Order, trading_market_config: SymbolMarketConfig, auto_exit_reason: AutoExitReason
    ) -> float:
        if auto_exit_reason.percent_to_sell < 100:
            final_amount_to_sell = self._floor_round(
                sell_order.amount * (auto_exit_reason.percent_to_sell / 100),
                ndigits=trading_market_config.price_precision,
            )
        else:
            final_amount_to_sell = sell_order.amount
        return final_amount_to_sell
