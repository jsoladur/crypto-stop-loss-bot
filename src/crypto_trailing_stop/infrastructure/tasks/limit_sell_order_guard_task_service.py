import logging
from datetime import UTC, datetime
from typing import override

from aiogram import html
from apscheduler.triggers.interval import IntervalTrigger
from httpx import AsyncClient

from crypto_trailing_stop.commons.constants import (
    DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE,
    NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL,
)
from crypto_trailing_stop.config import get_configuration_properties
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderDto, CreateNewBit2MeOrderDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum, PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.enums.candlestick_enum import CandleStickEnum
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.market_signal_service import MarketSignalService
from crypto_trailing_stop.infrastructure.services.orders_analytics_service import OrdersAnalyticsService
from crypto_trailing_stop.infrastructure.services.stop_loss_percent_service import StopLossPercentService
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.infrastructure.services.vo.crypto_market_metrics import CryptoMarketMetrics
from crypto_trailing_stop.infrastructure.services.vo.limit_sell_order_guard_metrics import LimitSellOrderGuardMetrics
from crypto_trailing_stop.infrastructure.tasks.base import AbstractTradingTaskService
from crypto_trailing_stop.infrastructure.tasks.vo.auto_exit_reason import AutoExitReason
from crypto_trailing_stop.infrastructure.tasks.vo.technical_indicators_cache_item import TechnicalIndicatorsCacheItem

logger = logging.getLogger(__name__)


class LimitSellOrderGuardTaskService(AbstractTradingTaskService):
    def __init__(self):
        super().__init__()
        self._configuration_properties = get_configuration_properties()
        self._market_signal_service = MarketSignalService()
        self._ccxt_remote_service = CcxtRemoteService()
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
        previous_used_buy_trade_ids: set[str] = set()
        for sell_order in opened_sell_orders:
            try:
                previous_used_buy_trade_ids, *_ = await self._handle_single_sell_order(
                    sell_order, current_tickers_by_symbol, previous_used_buy_trade_ids, client=client
                )
            except Exception as e:
                logger.error(str(e), exc_info=True)
                await self._notify_fatal_error_via_telegram(e)

    async def _handle_single_sell_order(
        self,
        sell_order: Bit2MeOrderDto,
        current_tickers_by_symbol: dict[str, Bit2MeTickersDto],
        previous_used_buy_trade_ids: set[str],
        *,
        client: AsyncClient,
    ) -> set[str]:
        technical_indicators = self._technical_indicators_by_symbol_cache[sell_order.symbol].technical_indicators
        last_candle_market_metrics = CryptoMarketMetrics.from_candlestick(
            sell_order.symbol, candlestick=technical_indicators.iloc[CandleStickEnum.LAST]
        )
        *_, fiat_currency = sell_order.symbol.split("/")
        (
            guard_metrics,
            previous_used_buy_trade_ids,
        ) = await self._orders_analytics_service.calculate_guard_metrics_by_sell_order(
            sell_order,
            technical_indicators=technical_indicators,
            previous_used_buy_trade_ids=previous_used_buy_trade_ids,
            client=client,
        )
        tickers = current_tickers_by_symbol[sell_order.symbol]
        tickers_close_formatted = round(
            tickers.close,
            ndigits=NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(sell_order.symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE),
        )
        logger.info(
            f"Supervising {sell_order.order_type.upper()} SELL order {repr(sell_order)}: "
            + f"Avg Buy Price = {guard_metrics.avg_buy_price} {fiat_currency} / "
            + f"Break-Even Price = {guard_metrics.break_even_price} {fiat_currency} / "
            + f"Safeguard Stop Price = {guard_metrics.safeguard_stop_price} {fiat_currency} / "
            + f"ATR Take Profit Limit price = {guard_metrics.suggested_take_profit_limit_price} {fiat_currency} / "
            + f"ATR value = {guard_metrics.current_attr_value} {fiat_currency} / "
            + f"Current Price = {tickers_close_formatted} {fiat_currency}"
        )
        auto_exit_reason = await self._is_moment_to_exit(sell_order, tickers, guard_metrics, last_candle_market_metrics)
        if auto_exit_reason.is_exit:
            # Cancel current take-profit sell limit order
            await self._bit2me_remote_service.cancel_order_by_id(sell_order.id, client=client)
            new_market_order = await self._bit2me_remote_service.create_order(
                order=CreateNewBit2MeOrderDto(
                    order_type="market",
                    side=sell_order.side,
                    symbol=sell_order.symbol,
                    amount=str(sell_order.order_amount),
                ),
                client=client,
            )
            logger.info(
                f"[LIMIT SELL ORDER GUARD] NEW MARKET ORDER Id: '{new_market_order.id}', for selling everything immediately!"  # noqa: E501
            )
            await self._notify_new_market_order_created_via_telegram(
                new_market_order,
                current_symbol_price=tickers.close,
                guard_metrics=guard_metrics,
                auto_exit_reason=auto_exit_reason,
            )
        return (previous_used_buy_trade_ids,)

    async def _is_moment_to_exit(
        self,
        sell_order: Bit2MeOrderDto,
        tickers: Bit2MeTickersDto,
        guard_metrics: LimitSellOrderGuardMetrics,
        last_candle_market_metrics: CryptoMarketMetrics,
    ) -> AutoExitReason:
        # XXX: [JMSOLA] In this point we have to think over about how to make a good exit when
        # our order has not been filled but suddlenly appear a SELL 1H signal, so we need to define
        # a strategy to immediately exit because our high limit price won't be reached!
        safeguard_stop_price_reached = tickers.close <= guard_metrics.safeguard_stop_price
        auto_exit_sell_1h, atr_take_profit_limit_price_reached = False, False
        if not safeguard_stop_price_reached:
            crypto_currency, *_ = sell_order.symbol.split("/")
            buy_sell_signals_config = await self._buy_sell_signals_config_service.find_by_symbol(crypto_currency)
            # Calculate auto_exit_sell_1h
            auto_exit_sell_1h = await self._is_auto_exit_due_to_sell_1h(
                sell_order, tickers, guard_metrics, buy_sell_signals_config, last_candle_market_metrics
            )
            if not auto_exit_sell_1h:
                atr_take_profit_limit_price_reached = (
                    await self._is_auto_exit_due_to_atr_take_profit_limit_price_reached(
                        sell_order, tickers, guard_metrics, buy_sell_signals_config, last_candle_market_metrics
                    )
                )
        return AutoExitReason(
            safeguard_stop_price_reached=safeguard_stop_price_reached,
            auto_exit_sell_1h=auto_exit_sell_1h,
            atr_take_profit_limit_price_reached=atr_take_profit_limit_price_reached,
        )

    async def _is_auto_exit_due_to_sell_1h(
        self,
        sell_order: Bit2MeOrderDto,
        tickers: Bit2MeTickersDto,
        guard_metrics: LimitSellOrderGuardMetrics,
        buy_sell_signals_config: BuySellSignalsConfigItem,
        last_candle_market_metrics: CryptoMarketMetrics,
    ) -> bool:
        auto_exit_sell_1h = False
        if buy_sell_signals_config.auto_exit_sell_1h:
            last_market_1h_signal = await self._market_signal_service.find_last_market_signal(sell_order.symbol)
            auto_exit_sell_1h = bool(
                last_market_1h_signal is not None
                and last_market_1h_signal.timestamp > sell_order.created_at
                and last_market_1h_signal.signal_type == "sell"
                and tickers.close >= guard_metrics.break_even_price
                and last_candle_market_metrics.macd_hist < 0
            )
        return auto_exit_sell_1h

    async def _is_auto_exit_due_to_atr_take_profit_limit_price_reached(
        self,
        _: Bit2MeOrderDto,
        tickers: Bit2MeTickersDto,
        guard_metrics: LimitSellOrderGuardMetrics,
        buy_sell_signals_config: BuySellSignalsConfigItem,
        __: CryptoMarketMetrics,
    ) -> bool:
        atr_take_profit_limit_price_reached = False
        if buy_sell_signals_config.auto_exit_atr_take_profit:
            # Ensuring we are not selling below the break even price,
            # regardless what the ATR Take profit limit price is!
            atr_take_profit_limit_price_reached = bool(
                tickers.close >= guard_metrics.break_even_price
                and tickers.close >= guard_metrics.suggested_take_profit_limit_price
            )
        return atr_take_profit_limit_price_reached

    async def _notify_new_market_order_created_via_telegram(
        self,
        new_market_order: Bit2MeOrderDto,
        *,
        current_symbol_price: float | int,
        guard_metrics: LimitSellOrderGuardMetrics,
        auto_exit_reason: AutoExitReason,
    ) -> None:
        crypto_currency, fiat_currency = new_market_order.symbol.split("/")
        text_message = f"🚨 {html.bold('MARKET SELL ORDER FILLED')} 🚨\n\n"
        text_message += f"{new_market_order.order_amount} {crypto_currency} HAS BEEN SOLD due to:\n"
        details = self._get_notification_message_details(
            current_symbol_price, guard_metrics, auto_exit_reason, crypto_currency, fiat_currency
        )
        text_message += f"* {html.italic(details)}"
        await self._notify_alert_by_type(
            PushNotificationTypeEnum.LIMIT_SELL_ORDER_GUARD_EXECUTED_ALERT, message=text_message
        )

    def _get_notification_message_details(
        self,
        current_symbol_price: float | int,
        guard_metrics: LimitSellOrderGuardMetrics,
        auto_exit_reason: AutoExitReason,
        crypto_currency: str,
        fiat_currency: str,
    ) -> str:
        if auto_exit_reason.safeguard_stop_price_reached:
            details = (
                f"Current {crypto_currency} price ({current_symbol_price} {fiat_currency}) "
                + f"is lower than the safeguard calculated ({guard_metrics.safeguard_stop_price} {fiat_currency})."
            )
        elif auto_exit_reason.auto_exit_sell_1h:
            details = (
                f"At current {crypto_currency} price ({current_symbol_price} {fiat_currency}), "
                + "a SELL 1H signal has suddenly appeared."
            )
        elif auto_exit_reason.atr_take_profit_limit_price_reached:
            details = (
                f"Current {crypto_currency} price ({current_symbol_price} {fiat_currency}) "
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
