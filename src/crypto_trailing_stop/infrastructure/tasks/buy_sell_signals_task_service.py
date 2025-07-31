import logging
from datetime import UTC, datetime
from typing import get_args, override

import ccxt.async_support as ccxt
import pandas as pd
import pydash
from aiogram import html
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from httpx import AsyncClient

from crypto_trailing_stop.commons.constants import (
    BUY_SELL_MINUTES_PAST_HOUR_EXECUTION_CRON_PATTERN,
    SIGNALS_EVALUATION_RESULT_EVENT_NAME,
)
from crypto_trailing_stop.config import get_configuration_properties, get_event_emitter
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_market_config_dto import Bit2MeMarketConfigDto
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum, PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.enums.candlestick_enum import CandleStickEnum
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.push_notification_service import PushNotificationService
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.infrastructure.services.vo.crypto_market_metrics import CryptoMarketMetrics
from crypto_trailing_stop.infrastructure.tasks.base import AbstractTaskService
from crypto_trailing_stop.infrastructure.tasks.vo.signals_evaluation_result import SignalsEvaluationResult
from crypto_trailing_stop.infrastructure.tasks.vo.types import RSIState, Timeframe

logger = logging.getLogger(__name__)


class BuySellSignalsTaskService(AbstractTaskService):
    def __init__(self):
        super().__init__()
        self._configuration_properties = get_configuration_properties()
        self._event_emitter = get_event_emitter()
        self._bit2me_remote_service = Bit2MeRemoteService()
        self._ccxt_remote_service = CcxtRemoteService()
        self._global_flag_service = GlobalFlagService()
        self._push_notification_service = PushNotificationService()
        self._crypto_analytics_service = CryptoAnalyticsService(
            bit2me_remote_service=self._bit2me_remote_service,
            ccxt_remote_service=self._ccxt_remote_service,
            buy_sell_signals_config_service=BuySellSignalsConfigService(
                bit2me_remote_service=self._bit2me_remote_service
            ),
        )
        self._exchange = self._ccxt_remote_service.get_exchange()
        self._last_signal_evalutation_result_cache: dict[str, SignalsEvaluationResult] = {}
        self._job = self._create_job()

    @override
    async def start(self) -> None:
        """
        Start method does not do anything,
        this job will be running every time to collect buy/sell signals
        """

    @override
    async def stop(self) -> None:
        """
        Start method does not do anything,
        this job will be running every time to collect buy/sell signals
        """

    @override
    async def _run(self) -> None:
        async with await self._bit2me_remote_service.get_http_client() as client:
            favourite_tickers_list = await self._crypto_analytics_service.get_favourite_tickers(client=client)
            current_tickers_by_symbol: dict[str, Bit2MeTickersDto] = {
                tickers.symbol: tickers for tickers in favourite_tickers_list
            }
            symbol_timeframe_tuples = [
                (symbol, timeframe)
                for symbol in list(current_tickers_by_symbol.keys())
                for timeframe in get_args(Timeframe)
            ]
            async with self._exchange as exchange:
                for current_symbol, current_timeframe in symbol_timeframe_tuples:
                    try:
                        await self._eval_and_notify_signals(
                            symbol=current_symbol,
                            timeframe=current_timeframe,
                            tickers=current_tickers_by_symbol[current_symbol],
                            client=client,
                            exchange=exchange,
                        )
                    except Exception as e:  # pragma: no cover
                        logger.error(str(e), exc_info=True)
                        await self._notify_fatal_error_via_telegram(e)

    @override
    def get_global_flag_type(self) -> GlobalFlagTypeEnum:
        return GlobalFlagTypeEnum.BUY_SELL_SIGNALS

    @override
    def _get_job_trigger(self) -> CronTrigger | IntervalTrigger:  # pragma: no cover
        if self._configuration_properties.buy_sell_signals_run_via_cron_pattern:
            trigger = CronTrigger(
                minute=",".join([str(minute) for minute in BUY_SELL_MINUTES_PAST_HOUR_EXECUTION_CRON_PATTERN]), hour="*"
            )
        else:
            trigger = IntervalTrigger(seconds=self._configuration_properties.job_interval_seconds)
        return trigger

    async def _eval_and_notify_signals(
        self, symbol: str, timeframe: Timeframe, tickers: Bit2MeTickersDto, client: AsyncClient, exchange: ccxt.Exchange
    ) -> None:
        trading_market_config = await self._bit2me_remote_service.get_trading_market_config_by_symbol(
            symbol, client=client
        )
        (
            df_with_indicators,
            buy_sell_signals_config,
        ) = await self._crypto_analytics_service.calculate_technical_indicators(
            symbol, timeframe=timeframe, client=client, exchange=exchange
        )
        # Use the default, wider threshold for 4H signals
        signals = self._check_signals(
            symbol, timeframe, df_with_indicators, buy_sell_signals_config, trading_market_config=trading_market_config
        )
        is_new_signals, previous_signals = self._is_new_signals(signals)
        if is_new_signals:
            try:
                is_enabled_for = await self._global_flag_service.is_enabled_for(self.get_global_flag_type())
                if is_enabled_for:
                    telegram_chat_ids = await self._push_notification_service.get_actived_subscription_by_type(
                        notification_type=PushNotificationTypeEnum.BUY_SELL_STRATEGY_ALERT
                    )
                    if telegram_chat_ids:
                        logger.info(
                            f"Notifying new signals to the Telegram Chat ids: {', '.join(map(lambda tci: str(tci), telegram_chat_ids))}!!"  # noqa: E501
                        )
                        base_symbol = symbol.split("/")[0].strip().upper()
                        # 1. Report RSI Anticipation Zones
                        if signals.is_anticipation_zone:
                            await self._notify_anticipation_zone_alerts(
                                signals,
                                previous_signals,
                                telegram_chat_ids=telegram_chat_ids,
                                timeframe=timeframe,
                                tickers=tickers,
                                base_symbol=base_symbol,
                            )
                        # 2. Report Confirmation Signals (now identical for both timeframes)
                        elif signals.is_reliable:
                            await self._notify_reliable_alerts(
                                signals,
                                telegram_chat_ids=telegram_chat_ids,
                                timeframe=timeframe,
                                tickers=tickers,
                                base_symbol=base_symbol,
                            )
            finally:
                self._event_emitter.emit(SIGNALS_EVALUATION_RESULT_EVENT_NAME, signals)
        else:  # pragma: no cover
            logger.info("Calculated signals were already notified previously!")

    def _is_new_signals(self, current_signals: SignalsEvaluationResult) -> tuple[bool, SignalsEvaluationResult | None]:
        is_new_signals = current_signals.cache_key not in self._last_signal_evalutation_result_cache
        previous_signals: SignalsEvaluationResult | None = None
        if not is_new_signals:  # pragma: no cover
            previous_signals = self._last_signal_evalutation_result_cache[current_signals.cache_key]
            is_new_signals = previous_signals != current_signals
            logger.info(f"Previous ({repr(previous_signals)}) != Current ({repr(current_signals)}) ? {is_new_signals}")
        self._last_signal_evalutation_result_cache[current_signals.cache_key] = current_signals
        return is_new_signals, previous_signals

    def _check_signals(
        self,
        symbol: str,
        timeframe: Timeframe,
        df: pd.DataFrame,
        buy_sell_signals_config: BuySellSignalsConfigItem,
        *,
        trading_market_config: Bit2MeMarketConfigDto,
    ) -> SignalsEvaluationResult:
        timestamp = datetime.now(tz=UTC).timestamp()
        buy_signal, sell_signal, is_choppy = False, False, False
        atr, closing_price, ema_long_price = 0.0, 0.0, 0.0
        rsi_state = "neutral"
        # Use a threshold of 0 for 1H signals to disable the proximity check
        volatility_threshold = self._get_volatility_threshold(timeframe)
        # Last confirmed candle
        last_candle_market_metrics = CryptoMarketMetrics.from_candlestick(
            symbol, df.iloc[CandleStickEnum.LAST], trading_market_config=trading_market_config
        )
        # Update timestamp
        timestamp = last_candle_market_metrics.timestamp.timestamp()
        # Calculate RSI Anticipation Zone (RSI)
        rsi_state = last_candle_market_metrics.rsi_state
        # Rounded metrics
        rounded_last_candle_market_metrics = last_candle_market_metrics.rounded(trading_market_config)
        atr = rounded_last_candle_market_metrics.atr
        closing_price = rounded_last_candle_market_metrics.closing_price
        ema_long_price = rounded_last_candle_market_metrics.ema_long

        min_volatility_threshold = last_candle_market_metrics.closing_price * volatility_threshold

        is_choppy = bool(last_candle_market_metrics.atr < min_volatility_threshold)
        if is_choppy:
            logger.info(
                f"{symbol} - ({timeframe.upper()}) :: "
                + f"Market too choppy (ATR {last_candle_market_metrics.atr} < Threshold {min_volatility_threshold}). "  # noqa: E501
                + "Skipping signal check..."
            )
        else:
            logger.info(
                f"{symbol} - ({timeframe.upper()}) :: "
                + f"Market is trending (ATR {last_candle_market_metrics.atr} >= Threshold {min_volatility_threshold}). "  # noqa: E501
                + "Checking for signals..."
            )
            # Prev confirmed candle
            prev_candle_market_metrics = CryptoMarketMetrics.from_candlestick(
                symbol, df.iloc[CandleStickEnum.PREV], trading_market_config=trading_market_config
            )
            # A proximity_threshold of 0 effectively disables the proximity check
            buy_signal = self._calculate_buy_signal(
                oldest_candle_market_metrics=CryptoMarketMetrics.from_candlestick(
                    symbol, df.iloc[CandleStickEnum.OLDEST], trading_market_config=trading_market_config
                ),
                prior_candle_market_metrics=CryptoMarketMetrics.from_candlestick(
                    symbol, df.iloc[CandleStickEnum.PRIOR], trading_market_config=trading_market_config
                ),
                prev_candle_market_metrics=prev_candle_market_metrics,
                last_candle_market_metrics=last_candle_market_metrics,
                buy_sell_signals_config=buy_sell_signals_config,
            )
            # Sell Signal Logic
            sell_signal = self._calculate_sell_signal(prev_candle_market_metrics, last_candle_market_metrics)
        ret = SignalsEvaluationResult(
            timestamp=timestamp,
            symbol=symbol,
            timeframe=timeframe,
            buy=buy_signal,
            sell=sell_signal,
            rsi_state=rsi_state,
            is_choppy=is_choppy,
            atr=atr,
            closing_price=closing_price,
            ema_long_price=ema_long_price,
        )
        return ret

    def _calculate_buy_signal(
        self,
        *,
        oldest_candle_market_metrics: CryptoMarketMetrics,
        prior_candle_market_metrics: CryptoMarketMetrics,
        prev_candle_market_metrics: CryptoMarketMetrics,
        last_candle_market_metrics: CryptoMarketMetrics,
        buy_sell_signals_config: BuySellSignalsConfigItem,
    ) -> bool:
        """
        Calculates the buy signal, including the 2-candle delayed confirmation logic
        when ADX filter is enabled.
        """
        # 1. Check for the "Immediate Signal" (crossover on the last candle).
        ema_bullish_cross_on_last = self._is_ema_bullish_crossover(
            earlier_candle=prev_candle_market_metrics, later_candle=last_candle_market_metrics
        )
        is_trend_momentum_confirmed_on_last = self._is_trend_momentum_confirmed(
            candle=last_candle_market_metrics, buy_sell_signals_config=buy_sell_signals_config
        )
        buy_signal = ema_bullish_cross_on_last and is_trend_momentum_confirmed_on_last
        # If the ADX filter is off, we only check for the immediate signal.
        if buy_sell_signals_config.filter_noise_using_adx:
            # --- ADX filter is ON from this point forward ---
            # 2. Check for a "Delayed Signal" from 1 candle ago.
            ema_bullish_cross_on_prev = self._is_ema_bullish_crossover(
                earlier_candle=prior_candle_market_metrics, later_candle=prev_candle_market_metrics
            )
            is_trend_momentum_confirmed_on_prev = self._is_trend_momentum_confirmed(
                candle=prev_candle_market_metrics, buy_sell_signals_config=buy_sell_signals_config
            )
            signal_delayed_1_ago = (
                ema_bullish_cross_on_prev
                and is_trend_momentum_confirmed_on_last
                and not is_trend_momentum_confirmed_on_prev
            )
            # 3. Check for a "Delayed Signal" from 2 candles ago.
            is_trend_momentum_confirmed_on_prior = self._is_trend_momentum_confirmed(
                candle=prior_candle_market_metrics, buy_sell_signals_config=buy_sell_signals_config
            )
            ema_bullish_cross_on_prior = self._is_ema_bullish_crossover(
                earlier_candle=oldest_candle_market_metrics, later_candle=prior_candle_market_metrics
            )
            signal_delayed_2_ago = (
                ema_bullish_cross_on_prior
                and is_trend_momentum_confirmed_on_last
                and not is_trend_momentum_confirmed_on_prev  # Must not have been valid on prev candle
                and not is_trend_momentum_confirmed_on_prior  # Must not have been valid on its own candle
            )
            # 4. The final signal is true if the immediate OR any valid delayed signal is found.
            signal_delayed = signal_delayed_1_ago or signal_delayed_2_ago
            buy_signal = buy_signal or signal_delayed
        return bool(buy_signal)

    def _calculate_sell_signal(
        self, prev_candle_market_metrics: CryptoMarketMetrics, last_candle_market_metrics: CryptoMarketMetrics
    ) -> bool:
        ema_bearish_cross = (
            prev_candle_market_metrics.ema_short >= prev_candle_market_metrics.ema_mid
            and last_candle_market_metrics.ema_short < last_candle_market_metrics.ema_mid
        )
        # XXX: [JMSOLA] Removed ADX filter for sell signals
        # This is because we want to capture the bearish trend even if the ADX is not strong.
        is_strong_downtrend = True  # Always consider the trend strong for sell signals
        # is_strong_downtrend = not buy_sell_signals_config.filter_noise_using_adx or (
        #     # NOTE: -DI > +DI
        #     last_candle_market_metrics.adx_neg > last_candle_market_metrics.adx_pos
        #     # NOTE: ADX > 20
        #     and last_candle_market_metrics.adx > self._configuration_properties.buy_sell_signals_adx_threshold
        # )
        sell_signal = ema_bearish_cross and last_candle_market_metrics.macd_hist < 0 and is_strong_downtrend
        return bool(sell_signal)

    def _get_volatility_threshold(self, timeframe: Timeframe) -> float:
        # XXX: [JMSOLA] Volatility Filter Logic
        # Only proceed if the market has meaningful volatility.
        # Here, we define "meaningful" as an ATR value that is at least 0.5% of the closing price
        # for 4h period, and 0.3% of the closing price for 1h periodº
        volatility_threshold = (
            self._configuration_properties.buy_sell_signals_4h_volatility_threshold
            if timeframe == "4h"
            else self._configuration_properties.buy_sell_signals_1h_volatility_threshold
        )
        return volatility_threshold

    async def _notify_anticipation_zone_alerts(
        self,
        signals: SignalsEvaluationResult,
        previous_signals: SignalsEvaluationResult | None,
        *,
        telegram_chat_ids: list[str],
        timeframe: Timeframe,
        tickers: Bit2MeTickersDto,
        base_symbol: str,
    ) -> None:
        if (previous_signals is None and signals.rsi_state != "neutral") or (
            previous_signals is not None and signals.rsi_state != previous_signals.rsi_state
        ):
            await self._notify_rsi_state_alert(
                rsi_state=signals.rsi_state,
                previous_rsi_state=previous_signals.rsi_state if previous_signals else None,
                base_symbol=base_symbol,
                telegram_chat_ids=telegram_chat_ids,
                timeframe=timeframe,
                tickers=tickers,
            )
        else:  # pragma: no cover
            logger.info(f"Neutral market for {base_symbol} on {timeframe}.")

    async def _notify_reliable_alerts(
        self,
        signals: SignalsEvaluationResult,
        *,
        telegram_chat_ids: list[str],
        timeframe: Timeframe,
        tickers: Bit2MeTickersDto,
        base_symbol: str,
    ) -> None:
        if signals.is_choppy:
            message = (
                f"🟡 - 🫥 {html.bold('CHOPPY MARKET ' + '(' + timeframe.upper() + ')')} for {html.bold(base_symbol)}.\n"  # noqa: E501
                + "🤫 Volatility is low. DO NOT ACT! 🤫"
            )
            await self._notify_alert(telegram_chat_ids, message, tickers=tickers)
        elif signals.buy:
            await self._notify_buy_alert(
                telegram_chat_ids=telegram_chat_ids, timeframe=timeframe, tickers=tickers, base_symbol=base_symbol
            )
        elif signals.sell:
            await self._notify_sell_alert(
                telegram_chat_ids=telegram_chat_ids, timeframe=timeframe, tickers=tickers, base_symbol=base_symbol
            )
        else:
            logger.info(f"No new confirmation signals on the {timeframe} timeframe for {base_symbol}.")

    async def _notify_rsi_state_alert(
        self,
        *,
        rsi_state: RSIState,
        previous_rsi_state: RSIState | None,
        base_symbol: str,
        telegram_chat_ids: list[str],
        timeframe: Timeframe,
        tickers: Bit2MeTickersDto,
    ) -> None:
        if rsi_state == "neutral":
            icon = "🧘"
            message_title = "RSI BACK TO NEUTRAL 🧘"
            description = (
                f"RSI transitioned from {html.bold(pydash.start_case(previous_rsi_state))} to "
                + f"{html.bold(pydash.start_case(rsi_state))}. "
                + f"{html.bold('No strong momentum currently detected')}."
            )
            if previous_rsi_state in {"bullish_momentum", "overbought"}:
                description += f"\n⚠️ {html.bold('If you bought during the uptrend, consider taking profits, as the momentum is fading.')}"  # noqa: E501
        if rsi_state == "bullish_momentum":
            icon = "💪"
            message_title = "BULLISH MOMENTUM ANTICIPATION 💪"
            description = (
                "🔥 Bullish Momentum! RSI is high in a strong uptrend. 🔥"
                + f" {html.bold('This confirms trend strength. DO NOT SELL.')}"
            )
        elif rsi_state == "overbought":
            icon = "📈"
            message_title = "Pre-SELL ⚠️ Warning ⚠️ "
            description = (
                "🥵 Market is Overbought (RSI &gt; 70). Trend may be exhausted 🥵."
                + f" {html.bold('Watch for a confirmation SELL signal')}."
            )
        elif rsi_state == "oversold":
            icon = "📉"
            message_title = "Pre-BUY ⚠️ Warning ⚠️ "
            description = (
                "🥶 Market is Oversold (RSI &lt; 30). Selling may be exhausted 🥶."
                + f" {html.bold('Get ready for a potential BUY signal')}."
            )
        message = (
            f"{icon} {html.bold(message_title + ' (' + timeframe.upper() + ')')} "
            + f"for {html.bold(base_symbol)}\n{description}"
        )
        await self._notify_alert(telegram_chat_ids, message, tickers=tickers)

    async def _notify_buy_alert(
        self, *, telegram_chat_ids: list[str], timeframe: Timeframe, tickers: Bit2MeTickersDto, base_symbol: str
    ) -> None:
        if timeframe == "4h":
            message = (
                f"⏬⏬ - ⚠️ {html.bold('UPTREND EXHAUSTION ALERT (4H)')} for {html.bold(base_symbol)}\n"
                f"{html.bold('The Uptrend may be maturing and ending')}. "
                + f"Wait for a {html.bold('SELL 1H signal')} in order to sell, "
                + "since a new bearish trend could be coming!"
            )
        else:
            message = (
                f"🟢 - 🛒 {html.bold('BUY SIGNAL ' + '(' + timeframe.upper() + ')')} for {html.bold(base_symbol)}!"  # noqa: E501
            )
        await self._notify_alert(telegram_chat_ids, message, tickers=tickers)

    async def _notify_sell_alert(
        self, *, telegram_chat_ids: list[str], timeframe: Timeframe, tickers: Bit2MeTickersDto, base_symbol: str
    ) -> None:
        if timeframe == "4h":
            message = (
                f"🚀🚀 - 🟢 - {html.bold('DOWNTREND EXHAUSTION ALERT (4H)')} for {html.bold(base_symbol)}\n"
                f"{html.bold('The DownTrend may be maturing and ending')}. "
                + f"Wait for a {html.bold('BUY 1H signal')} in order to buy, "
                + "it could be the moment for a new bullish period."
            )
        else:
            message = (
                f"🔴 - 🔚 {html.bold('SELL SIGNAL ' + '(' + timeframe.upper() + ')')} for {html.bold(base_symbol)}. "
                f"{html.italic('Sell only if price > break-even; otherwise, hold for stop loss.')}"
            )
        await self._notify_alert(telegram_chat_ids, message, tickers=tickers)

    async def _notify_alert(
        self, telegram_chat_ids: list[str], body_message: str, *, tickers: Bit2MeTickersDto
    ) -> None:
        crypto_currency, fiat_currency = tickers.symbol.split("/")
        message = f"⚡⚡ {html.bold('ATTENTION')} ⚡⚡\n\n"
        message += f"{body_message}\n"
        message += html.bold(f"🔥 {crypto_currency} current price is {tickers.close} {fiat_currency}")
        for tg_chat_id in telegram_chat_ids:
            await self._telegram_service.send_message(chat_id=tg_chat_id, text=message)

    def _is_trend_momentum_confirmed(
        self, *, candle: CryptoMarketMetrics, buy_sell_signals_config: BuySellSignalsConfigItem
    ) -> bool:
        """Checks if all non-crossover buy confirmations (MACD, ADX) are met for a given candle."""
        is_strong_uptrend = self._is_strong_uptrend(candle, buy_sell_signals_config)
        return candle.macd_hist > 0 and is_strong_uptrend

    def _is_strong_uptrend(
        self, candle: CryptoMarketMetrics, buy_sell_signals_config: BuySellSignalsConfigItem
    ) -> bool:
        is_strong_uptrend = True
        if buy_sell_signals_config.filter_noise_using_adx:
            # NOTE: ADX > 20
            trend_strength_confirmed = candle.adx > buy_sell_signals_config.adx_threshold
            # NOTE: +DI > -DI
            di_cross_is_bullish = candle.adx_pos > candle.adx_neg
            # NOTE: MACD Line > 0 and Lowest Price > EMA Mid
            alternative_is_confirmed = candle.macd_line > 0 and candle.lowest_price > candle.ema_mid
            is_strong_uptrend = trend_strength_confirmed and (di_cross_is_bullish or alternative_is_confirmed)
        return is_strong_uptrend

    def _is_ema_bullish_crossover(
        self, *, earlier_candle: CryptoMarketMetrics, later_candle: CryptoMarketMetrics
    ) -> bool:
        return earlier_candle.ema_short <= earlier_candle.ema_mid and later_candle.ema_short > later_candle.ema_mid
