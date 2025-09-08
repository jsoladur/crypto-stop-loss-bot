import logging
from datetime import UTC, datetime
from typing import override

from aiogram import html
from apscheduler.triggers.interval import IntervalTrigger
from httpx import AsyncClient

from crypto_trailing_stop.commons.constants import LIMIT_SELL_ORDER_GUARD_SAFETY_FACTOR
from crypto_trailing_stop.config import get_configuration_properties
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto, CreateNewBit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum, PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.enums.candlestick_enum import CandleStickEnum
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.limit_sell_order_guard_cache_service import (
    LimitSellOrderGuardCacheService,
)
from crypto_trailing_stop.infrastructure.services.market_signal_service import MarketSignalService
from crypto_trailing_stop.infrastructure.services.orders_analytics_service import OrdersAnalyticsService
from crypto_trailing_stop.infrastructure.services.stop_loss_percent_service import StopLossPercentService
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.infrastructure.services.vo.crypto_market_metrics import CryptoMarketMetrics
from crypto_trailing_stop.infrastructure.services.vo.limit_sell_order_guard_metrics import LimitSellOrderGuardMetrics
from crypto_trailing_stop.infrastructure.tasks.base import AbstractTaskService
from crypto_trailing_stop.infrastructure.tasks.vo.auto_exit_reason import AutoExitReason
from crypto_trailing_stop.infrastructure.tasks.vo.technical_indicators_cache_item import TechnicalIndicatorsCacheItem

logger = logging.getLogger(__name__)


class LimitSellOrderGuardTaskService(AbstractTaskService):
    def __init__(self):
        super().__init__()
        self._configuration_properties = get_configuration_properties()
        self._market_signal_service = MarketSignalService()
        self._ccxt_remote_service = CcxtRemoteService()
        self._limit_sell_order_guard_cache_service = LimitSellOrderGuardCacheService()
        self._buy_sell_signals_config_service = BuySellSignalsConfigService(
            bit2me_remote_service=self._bit2me_remote_service
        )
        self._crypto_analytics_service = CryptoAnalyticsService(
            bit2me_remote_service=self._bit2me_remote_service,
            ccxt_remote_service=self._ccxt_remote_service,
            buy_sell_signals_config_service=self._buy_sell_signals_config_service,
        )
        self._orders_analytics_service = OrdersAnalyticsService(
            bit2me_remote_service=self._bit2me_remote_service,
            ccxt_remote_service=self._ccxt_remote_service,
            stop_loss_percent_service=StopLossPercentService(
                bit2me_remote_service=self._bit2me_remote_service, global_flag_service=GlobalFlagService()
            ),
            buy_sell_signals_config_service=self._buy_sell_signals_config_service,
            crypto_analytics_service=self._crypto_analytics_service,
        )
        self._exchange = self._ccxt_remote_service.get_exchange()
        self._technical_indicators_by_symbol_cache: dict[str, TechnicalIndicatorsCacheItem] = {}

    @override
    def get_global_flag_type(self) -> GlobalFlagTypeEnum:
        return GlobalFlagTypeEnum.LIMIT_SELL_ORDER_GUARD

    @override
    async def _run(self) -> None:
        async with await self._bit2me_remote_service.get_http_client() as client:
            sell_orders = await self._bit2me_remote_service.get_pending_sell_orders(client=client)
            if sell_orders:
                await self._handle_opened_sell_orders(sell_orders, client=client)
            else:  # pragma: no cover
                logger.info("There are no opened limit sell orders to handle! Let's see in the upcoming executions...")

    @override
    def _get_job_trigger(self) -> IntervalTrigger:
        return IntervalTrigger(seconds=self._configuration_properties.job_interval_seconds)

    async def _handle_opened_sell_orders(
        self, opened_sell_orders: list[Bit2MeOrderDto], *, client: AsyncClient
    ) -> None:
        # Refresh technical indicators if needed
        await self._refresh_technical_indicators_by_symbol_cache_if_needed(opened_sell_orders, client=client)
        # Get current tickers for getting closing prices
        current_tickers_by_symbol: dict[str, Bit2MeTickersDto] = await self._fetch_tickers_for_open_sell_orders(
            opened_sell_orders, client=client
        )
        previous_used_buy_trades: dict[str, float] = {}
        for sell_order in opened_sell_orders:
            try:
                previous_used_buy_trades, *_ = await self._handle_single_sell_order(
                    sell_order, current_tickers_by_symbol, previous_used_buy_trades, client=client
                )
            except Exception as e:  # pragma: no cover
                logger.error(str(e), exc_info=True)
                await self._notify_fatal_error_via_telegram(e)

    async def _handle_single_sell_order(
        self,
        sell_order: Bit2MeOrderDto,
        current_tickers_by_symbol: dict[str, Bit2MeTickersDto],
        previous_used_buy_trades: dict[str, float],
        *,
        client: AsyncClient,
    ) -> set[str]:
        crypto_currency, fiat_currency = sell_order.symbol.split("/")
        buy_sell_signals_config = await self._buy_sell_signals_config_service.find_by_symbol(crypto_currency)
        trading_market_config = await self._bit2me_remote_service.get_trading_market_config_by_symbol(
            sell_order.symbol, client=client
        )
        tickers = current_tickers_by_symbol[sell_order.symbol]
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
            previous_used_buy_trades=previous_used_buy_trades,
            client=client,
        )
        tickers_close_formatted = round(tickers.close, ndigits=trading_market_config.price_precision)
        logger.info(
            f"Supervising {sell_order.order_type.upper()} SELL order {repr(sell_order)} :: "
            + f"Avg Buy Price = {guard_metrics.avg_buy_price} {fiat_currency} / "
            + f"Break-Even Price = {guard_metrics.break_even_price} {fiat_currency} / "
            + f"Stop Loss = {guard_metrics.stop_loss_percent_value}% / "
            + f"Flex. Stop Loss = {guard_metrics.breathe_stop_loss_percent_value}% / "
            + f"Stop Price = {guard_metrics.safeguard_stop_price} {fiat_currency} / "
            + f"Flex. Stop Price = {guard_metrics.breathe_safeguard_stop_price} {fiat_currency} / "
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
            # Cancel current take-profit sell limit order
            await self._bit2me_remote_service.cancel_order_by_id(sell_order.id, client=client)
            if auto_exit_reason.percent_to_sell < 100:
                final_amount_to_sell = self._floor_round(
                    sell_order.order_amount * (auto_exit_reason.percent_to_sell / 100),
                    ndigits=trading_market_config.price_precision,
                )
            else:
                final_amount_to_sell = sell_order.order_amount
            # Create new market order
            new_market_order = await self._bit2me_remote_service.create_order(
                order=CreateNewBit2MeOrderDto(
                    order_type="limit",
                    side=sell_order.side,
                    symbol=sell_order.symbol,
                    price=str(
                        self._floor_round(
                            # XXX: [JMSOLA] Limit Sell order will be immediately filled
                            # since the price is less than the current bid/close one.
                            tickers.bid_or_close * LIMIT_SELL_ORDER_GUARD_SAFETY_FACTOR,
                            ndigits=trading_market_config.price_precision,
                        )
                    ),
                    amount=str(final_amount_to_sell),
                ),
                client=client,
            )
            logger.info(
                f"[LIMIT SELL ORDER GUARD] NEW MARKET ORDER Id: '{new_market_order.id}', "
                + f"for selling {auto_exit_reason.percent_to_sell}% "
                + f"of {sell_order.order_amount} {crypto_currency} immediately!"  # noqa: E501
            )
            if (remaining_amount := sell_order.order_amount - final_amount_to_sell) > 0:
                # NOTE: If we sold a percent less than 100.0%,
                #  we have to create again the sell order with the remaining order amount
                crypto_currency_wallet, *_ = await self._bit2me_remote_service.get_trading_wallet_balances(
                    symbols=crypto_currency, client=client
                )
                new_limit_sell_order_amount = self._floor_round(
                    min(crypto_currency_wallet.balance, remaining_amount),
                    ndigits=trading_market_config.amount_precision,
                )
                new_limit_sell_order = await self._bit2me_remote_service.create_order(
                    order=CreateNewBit2MeOrderDto(
                        order_type="limit",
                        side="sell",
                        symbol=sell_order.symbol,
                        price=str(
                            self._floor_round(
                                # XXX: [JMSOLA] Price is unreachable in purpose,
                                # for giving to the Limit Sell Order Guard the chance to
                                # operate properly
                                tickers.close * 2,
                                ndigits=trading_market_config.price_precision,
                            )
                        ),
                        amount=str(new_limit_sell_order_amount),
                    ),
                    client=client,
                )
                logger.info(
                    f"[LIMIT SELL ORDER GUARD] NEW LIMIT SELL ORDER Id: '{new_limit_sell_order.id}', "
                    + f"for selling continue monitoring the remaining {remaining_amount} {crypto_currency}!"
                )
            await self._notify_new_market_sell_order_created_via_telegram(
                new_market_order,
                tickers=tickers,
                last_candle_market_metrics=last_candle_market_metrics,
                guard_metrics=guard_metrics,
                auto_exit_reason=auto_exit_reason,
            )
        return (previous_used_buy_trades,)

    async def _is_moment_to_exit(
        self,
        *,
        sell_order: Bit2MeOrderDto,
        tickers: Bit2MeTickersDto,
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
        stop_loss_triggered, stop_loss_reached_at_closing_price, stop_loss_reached_at_current_price = (
            False,
            False,
            False,
        )
        take_profit_reached, exit_on_sell_signal, exit_on_bearish_divergence = (False, False, False)
        if not is_marked_for_immediate_sell:
            # Check if the safeguard stop price is reached
            stop_loss_triggered, stop_loss_reached_at_closing_price, stop_loss_reached_at_current_price = (
                self._is_stop_loss_triggered(
                    tickers=tickers, guard_metrics=guard_metrics, last_candle_market_metrics=last_candle_market_metrics
                )
            )
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
            stop_loss_reached_at_closing_price=stop_loss_reached_at_closing_price,
            stop_loss_reached_at_current_price=stop_loss_reached_at_current_price,
            exit_on_bearish_divergence=exit_on_bearish_divergence,
            exit_on_sell_signal=exit_on_sell_signal,
            take_profit_reached=take_profit_reached,
            percent_to_sell=percent_to_sell,
        )

    def _is_stop_loss_triggered(
        self,
        *,
        tickers: Bit2MeTickersDto,
        guard_metrics: LimitSellOrderGuardMetrics,
        last_candle_market_metrics: CryptoMarketMetrics,
    ) -> tuple[bool, bool, bool]:
        # XXX: [JMSOLA] Check if the safeguard stop price is reached
        # If the latest candle's closing price is below the safeguard stop price,
        # or the current sell price (bid) is below the breathe safeguard stop price
        # We want to give breathe room to the price to fluctuate
        stop_loss_reached_at_closing_price = bool(
            last_candle_market_metrics.closing_price < guard_metrics.safeguard_stop_price
        )
        stop_loss_reached_at_current_price = bool(tickers.bid_or_close < guard_metrics.breathe_safeguard_stop_price)
        stop_loss_triggered = stop_loss_reached_at_closing_price or stop_loss_reached_at_current_price
        return stop_loss_triggered, stop_loss_reached_at_closing_price, stop_loss_reached_at_current_price

    async def _should_auto_exit_on_sell_or_bearish_divergence_1h_signal(
        self,
        *,
        sell_order: Bit2MeOrderDto,
        tickers: Bit2MeTickersDto,
        guard_metrics: LimitSellOrderGuardMetrics,
        buy_sell_signals_config: BuySellSignalsConfigItem,
        prev_candle_market_metrics: CryptoMarketMetrics,
        last_candle_market_metrics: CryptoMarketMetrics,
    ) -> tuple[bool, bool]:
        exit_on_sell_signal, exit_on_bearish_divergence = False, False
        if buy_sell_signals_config.enable_exit_on_sell_signal:
            last_market_1h_signal = await self._market_signal_service.find_last_market_signal(sell_order.symbol)
            if (
                last_market_1h_signal is not None
                and last_market_1h_signal.timestamp > sell_order.created_at
                and tickers.bid_or_close >= guard_metrics.break_even_price
            ):  # Use bid for break-even check
                exit_on_bearish_divergence = bool(last_market_1h_signal.signal_type == "bearish_divergence")
                exit_on_sell_signal = bool(
                    last_market_1h_signal.signal_type == "sell"
                    and last_candle_market_metrics.macd_hist < 0
                    and last_candle_market_metrics.macd_hist < prev_candle_market_metrics.macd_hist
                )
        return exit_on_sell_signal, exit_on_bearish_divergence

    async def _should_auto_exit_on_take_profit_reached(
        self,
        *,
        tickers: Bit2MeTickersDto,
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

    async def _notify_new_market_sell_order_created_via_telegram(
        self,
        new_market_order: Bit2MeOrderDto,
        *,
        tickers: Bit2MeTickersDto,
        last_candle_market_metrics: Bit2MeTickersDto,
        guard_metrics: LimitSellOrderGuardMetrics,
        auto_exit_reason: AutoExitReason,
    ) -> None:
        crypto_currency, fiat_currency = new_market_order.symbol.split("/")
        text_message = f"🚨 {html.bold('MARKET SELL ORDER FILLED')} 🚨\n\n"
        text_message += f"{new_market_order.order_amount} {crypto_currency} HAS BEEN SOLD due to:\n"
        details = self._get_notification_message_details(
            tickers, last_candle_market_metrics, guard_metrics, auto_exit_reason, crypto_currency, fiat_currency
        )
        text_message += f"* {html.italic(details)}"
        await self._notify_alert_by_type(
            PushNotificationTypeEnum.LIMIT_SELL_ORDER_GUARD_EXECUTED_ALERT, message=text_message
        )

    def _get_notification_message_details(
        self,
        tickers: Bit2MeTickersDto,
        last_candle_market_metrics: CryptoMarketMetrics,
        guard_metrics: LimitSellOrderGuardMetrics,
        auto_exit_reason: AutoExitReason,
        crypto_currency: str,
        fiat_currency: str,
    ) -> str:
        if auto_exit_reason.is_marked_for_immediate_sell:
            details = (
                "Order was marked for immediate sell. Executing market order immediately at "
                + f"current {crypto_currency} price ({tickers.bid_or_close} {fiat_currency})."
            )
        elif auto_exit_reason.stop_loss_triggered:
            if auto_exit_reason.stop_loss_reached_at_closing_price:
                price_message = (
                    f"Closing {crypto_currency} price ({last_candle_market_metrics.closing_price} {fiat_currency})"
                )
                stop_price_message = (
                    f"safeguard stop price calculated ({guard_metrics.safeguard_stop_price} {fiat_currency})"
                )
            else:
                price_message = f"Current {crypto_currency} price ({tickers.bid_or_close} {fiat_currency})"
                stop_price_message = f"breathe safeguard stop price calculated ({guard_metrics.breathe_safeguard_stop_price} {fiat_currency})"  # noqa: E501
            details = f"{price_message} is lower than the {stop_price_message}."
        elif auto_exit_reason.exit_on_bearish_divergence:
            details = (
                f"At current {crypto_currency} price ({tickers.bid_or_close} {fiat_currency}), "
                + "a BEARISH DIVERGENCE signal has suddenly appeared."
            )
        elif auto_exit_reason.exit_on_sell_signal:
            details = (
                f"At current {crypto_currency} price ({tickers.bid_or_close} {fiat_currency}), "
                + "a SELL 1H signal has suddenly appeared."
            )
        elif auto_exit_reason.take_profit_reached:
            details = (
                f"Current {crypto_currency} price ({tickers.bid_or_close} {fiat_currency}) "
                + f"is higher than the ATR-based take profit calculated ({guard_metrics.suggested_take_profit_limit_price} {fiat_currency})."  # noqa: E501
            )
        return details

    async def _refresh_technical_indicators_by_symbol_cache_if_needed(
        self, opened_sell_orders: list[Bit2MeOrderDto], *, client: AsyncClient
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
