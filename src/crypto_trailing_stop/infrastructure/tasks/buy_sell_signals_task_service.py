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
    ANTICIPATION_ZONE_TIMEFRAMES,
    BUY_SELL_MINUTES_PAST_HOUR_EXECUTION_CRON_PATTERN,
    BUY_SELL_RELIABLE_TIMEFRAMES,
    DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE,
    NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL,
    SIGNALS_EVALUATION_RESULT_EVENT_NAME,
)
from crypto_trailing_stop.config import get_configuration_properties, get_event_emitter
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum, PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.enums.candlestick_enum import CandleStickEnum
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.push_notification_service import PushNotificationService
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
        df_with_indicators = await self._crypto_analytics_service.calculate_technical_indicators(
            symbol, timeframe=timeframe, client=client, exchange=exchange
        )
        # Use the default, wider threshold for 4H signals
        signals = self._check_signals(symbol, timeframe, df_with_indicators)
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
                        if timeframe in ANTICIPATION_ZONE_TIMEFRAMES:
                            await self._notify_anticipation_zone_alerts(
                                signals,
                                previous_signals,
                                telegram_chat_ids=telegram_chat_ids,
                                timeframe=timeframe,
                                tickers=tickers,
                                base_symbol=base_symbol,
                            )
                        # 2. Report Confirmation Signals (now identical for both timeframes)
                        elif timeframe in BUY_SELL_RELIABLE_TIMEFRAMES:
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

    def _check_signals(self, symbol: str, timeframe: Timeframe, df: pd.DataFrame) -> SignalsEvaluationResult:
        timestamp = datetime.now(tz=UTC).timestamp()
        buy_signal, sell_signal, is_choppy = False, False, False
        atr, closing_price, ema_long_price = 0.0, 0.0, 0.0
        rsi_state = "neutral"
        if len(df) >= 3:
            prev = df.iloc[CandleStickEnum.PREV]  # Prev confirmed candle
            last = df.iloc[CandleStickEnum.LAST]  # Last confirmed candle
            # Update timestamp
            timestamp = last["timestamp"].timestamp()
            # Calculate RSI Anticipation Zone (RSI)
            atr = round(
                last["atr"],
                ndigits=NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE),
            )
            closing_price = round(
                last["close"],
                ndigits=NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE),
            )
            ema_long_price = round(
                last["ema_long"],
                ndigits=NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE),
            )
            rsi_state = self._get_rsi_state(symbol, timeframe, last)
            # Use a threshold of 0 for 1H signals to disable the proximity check
            volatility_threshold = self._get_volatility_threshold(timeframe)
            min_volatility_threshold = last["close"] * volatility_threshold
            is_choppy = bool(last["atr"] < min_volatility_threshold)
            if is_choppy:
                logger.info(
                    f"{symbol} - ({timeframe.upper()}) :: "
                    + f"Market too choppy (ATR {last['atr']} < Threshold {min_volatility_threshold}). "
                    + "Skipping signal check..."
                )
            else:
                logger.info(
                    f"{symbol} - ({timeframe.upper()}) :: "
                    + f"Market is trending (ATR {last['atr']} >= Threshold {min_volatility_threshold}). "
                    + "Checking for signals..."
                )
                # A proximity_threshold of 0 effectively disables the proximity check
                buy_signal = self._calculate_buy_signal(prev, last)
                # Sell Signal Logic
                sell_signal = self._calculate_sell_signal(prev, last)
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

    def _calculate_buy_signal(self, prev: pd.Series, last: pd.Series) -> bool:
        # Buy Signal Logic
        ema_bullish_cross = prev["ema_short"] <= prev["ema_mid"] and last["ema_short"] > last["ema_mid"]
        buy_signal = ema_bullish_cross and last["macd_hist"] > 0
        return bool(buy_signal)

    def _calculate_sell_signal(self, prev: pd.Series, last: pd.Series) -> bool:
        ema_bearish_cross = prev["ema_short"] >= prev["ema_mid"] and last["ema_short"] < last["ema_mid"]
        sell_signal = ema_bearish_cross and last["macd_hist"] < 0

        return bool(sell_signal)

    def _get_rsi_state(self, symbol: str, timeframe: Timeframe, last: pd.Series) -> RSIState:
        crypto_market_metrics = CryptoMarketMetrics(
            symbol=symbol,
            closing_price=last["close"],
            ema_short=last["ema_short"],
            ema_mid=last["ema_mid"],
            ema_long=last["ema_long"],
            rsi=last["rsi"],
            atr=last["atr"],
        )
        return crypto_market_metrics.rsi_state

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
        else:
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
                f"🚀🚀 - 🟢 - {html.bold('STRATEGIC BUY ALERT (4H)')} for {html.bold(base_symbol)}\n"
                f"A BULLISH TREND is forming. {html.bold('DO NOT BUY YET!')}\n"
                f"Wait for a pullback and the next {html.bold('BUY 1H signal')} to find a good entry!"
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
                f"⏬⏬ - 🔴 - {html.bold('STRATEGIC SELL ALERT (4H)')} for {html.bold(base_symbol)}\n"
                f"A BEARISH TREND is forming. {html.bold('DO NOT SELL YET!')}\n"
                f"Wait for a bounce and the next {html.bold('SELL 1H signal')} to find a good exit!"
            )
        else:
            message = (
                f"🔴 - 🔚 {html.bold('SELL SIGNAL ' + '(' + timeframe.upper() + ')')} for {html.bold(base_symbol)}!"  # noqa: E501
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
