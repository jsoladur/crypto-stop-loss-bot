import logging
from datetime import UTC, datetime
from typing import Literal, override

import pandas as pd
from aiogram import html
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from ta.momentum import RSIIndicator
from ta.trend import MACD, EMAIndicator
from ta.volatility import AverageTrueRange  # Import ATR indicator

from crypto_trailing_stop.commons.constants import (
    BUY_SELL_ALERTS_TIMEFRAMES,
    BUY_SELL_MINUTES_PAST_HOUR_EXECUTION_CRON_PATTERN,
)
from crypto_trailing_stop.config import get_configuration_properties
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum, PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.push_notification_service import PushNotificationService
from crypto_trailing_stop.infrastructure.tasks.base import AbstractTaskService
from crypto_trailing_stop.infrastructure.tasks.vo.signals_evaluation_result import SignalsEvaluationResult

logger = logging.getLogger(__name__)


class BuySellSignalsTaskService(AbstractTaskService):
    def __init__(self):
        super().__init__()
        self._configuration_properties = get_configuration_properties()
        self._global_flag_service = GlobalFlagService()
        self._push_notification_service = PushNotificationService()
        self._ccxt_remote_service = CcxtRemoteService()
        self._last_signal_evalutation_result_cache: dict[str, SignalsEvaluationResult] = {}

    @override
    async def _run(self) -> None:
        is_buy_sell_signals_enabled = await self._global_flag_service.is_enabled_for(
            GlobalFlagTypeEnum.BUY_SELL_SIGNALS
        )
        if is_buy_sell_signals_enabled and (
            telegram_chat_ids := await self._push_notification_service.get_actived_subscription_by_type(
                notification_type=PushNotificationTypeEnum.BUY_SELL_STRATEGY_ALERT
            )
        ):
            await self._internal_run(telegram_chat_ids)
        else:
            logger.warning("[ATTENTION] Buy/Sell Signals job is DISABLED! You will not receive any alert!!")

    @override
    def _get_global_flag_type(self) -> GlobalFlagTypeEnum:
        return GlobalFlagTypeEnum.BUY_SELL_SIGNALS

    @override
    def _get_job_trigger(self) -> CronTrigger | IntervalTrigger:
        if self._configuration_properties.buy_sell_signals_run_via_cron_pattern:
            trigger = CronTrigger(
                minute=",".join([str(minute) for minute in BUY_SELL_MINUTES_PAST_HOUR_EXECUTION_CRON_PATTERN]), hour="*"
            )
        else:
            trigger = IntervalTrigger(seconds=self._configuration_properties.job_interval_seconds)
        return trigger

    async def _internal_run(self, telegram_chat_ids: list[int]) -> None:
        async with await self._bit2me_remote_service.get_http_client() as client:
            favourite_crypto_currencies = await self._bit2me_remote_service.get_favourite_crypto_currencies(
                client=client
            )
            bit2me_account_info = await self._bit2me_remote_service.get_account_info(client=client)
            symbols = [
                f"{crypto_currency}/{bit2me_account_info.profile.currency_code}"
                for crypto_currency in favourite_crypto_currencies
            ]

            current_tickers_by_symbol: dict[str, Bit2MeTickersDto] = await self._fetch_tickers_by_simbols(
                symbols, client=client
            )

            symbol_timeframe_tuples = [
                (symbol, timeframe) for symbol in symbols for timeframe in BUY_SELL_ALERTS_TIMEFRAMES
            ]
            for current_symbol, current_timeframe in symbol_timeframe_tuples:
                try:
                    await self._eval_and_notify_signals(
                        telegram_chat_ids,
                        symbol=current_symbol,
                        timeframe=current_timeframe,
                        tickers=current_tickers_by_symbol[current_symbol],
                    )
                except Exception as e:
                    logger.error(str(e), exc_info=True)
                    await self._notify_fatal_error_via_telegram(e)

    async def _eval_and_notify_signals(
        self, telegram_chat_ids: list[str], *, symbol: str, timeframe: Literal["4h", "1h"], tickers: Bit2MeTickersDto
    ) -> None:
        df = await self._ccxt_remote_service.fetch_ohlcv(symbol, timeframe)
        df_with_indicators = self._calculate_indicators(df)
        # Use the default, wider threshold for 4H signals
        # Use a threshold of 0 for 1H signals to disable the proximity check
        signals = self._check_signals(symbol, timeframe, df_with_indicators)
        if self._is_new_signals(signals):
            base_symbol = symbol.split("/")[0].strip().upper()
            # 1. Report RSI Anticipation Zones
            if signals.rsi_state != "neutral":
                icon = "📈" if signals.rsi_state == "overbought" else "📉"
                message = f"{icon} {html.bold('Anticipation Zone ' + '(' + timeframe.upper() + ')')} for {html.bold(base_symbol)} - RSI is {signals.rsi_state}!"  # noqa: E501
                await self._notify_alert(telegram_chat_ids, message, tickers=tickers)
            # 2. Report Confirmation Signals (now identical for both timeframes)
            if signals.is_choppy:
                message = (
                    f"🟡 - 🫥 {html.bold('CHOPPY MARKET ' + '(' + timeframe.upper() + ')')} for {html.bold(base_symbol)}.\n"  # noqa: E501
                    + "🤫 Volatility is low. DO NOT ACT! 🤫"
                )
                await self._notify_alert(telegram_chat_ids, message, tickers=tickers)
            elif not signals.buy or not signals.sell:
                if signals.buy:
                    message = f"🟢 - 🛒 {html.bold('BUY SIGNAL ' + '(' + timeframe.upper() + ')')} for {html.bold(base_symbol)}!"  # noqa: E501
                    await self._notify_alert(telegram_chat_ids, message, tickers=tickers)
                if signals.sell:
                    message = f"🔴 - 🔚 {html.bold('SELL SIGNAL ' + '(' + timeframe.upper() + ')')} for {html.bold(base_symbol)}!"  # noqa: E501
                    await self._notify_alert(telegram_chat_ids, message, tickers=tickers)
                if not signals.buy and not signals.sell:
                    logger.info(f"No new confirmation signals on the {timeframe} timeframe for {base_symbol}.")
        else:
            logger.info("Calculated signals were already notified previously!")

    def _is_new_signals(self, current_signals: SignalsEvaluationResult) -> bool:
        is_new_signals = current_signals.cache_key not in self._last_signal_evalutation_result_cache
        if not is_new_signals:
            previous_signals = self._last_signal_evalutation_result_cache[current_signals.cache_key]
            is_new_signals = previous_signals != current_signals
        self._last_signal_evalutation_result_cache[current_signals.cache_key] = current_signals
        return is_new_signals

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Calculating indicators...")
        # Exponential Moving Average (EMA) 9
        df["ema9"] = EMAIndicator(df["close"], window=9).ema_indicator()
        # Exponential Moving Average (EMA) 21
        df["ema21"] = EMAIndicator(df["close"], window=21).ema_indicator()
        # Exponential Moving Average (EMA) 200
        df["ema200"] = EMAIndicator(df["close"], window=200).ema_indicator()
        # Moving Average Convergence Divergence (MACD)
        macd = MACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
        df["macd_hist"] = macd.macd_diff()
        # Relative Strength Index (RSI)
        df["rsi"] = RSIIndicator(df["close"], window=14).rsi()
        # Average True Range (ATR)
        df["atr"] = AverageTrueRange(df["high"], df["low"], df["close"], window=14).average_true_range()
        df.dropna(inplace=True)
        df.reset_index(drop=True, inplace=True)
        logger.info("Indicator calculation complete.")
        return df

    def _check_signals(self, symbol: str, timeframe: Literal["4h", "1h"], df: pd.DataFrame) -> SignalsEvaluationResult:
        timestamp = datetime.now(tz=UTC).timestamp()
        buy_signal, sell_signal, is_choppy = False, False, False
        rsi_state = "neutral"
        if len(df) >= 2:
            last = df.iloc[-1]
            prev = df.iloc[-2]
            # Update timestamp
            timestamp = last["timestamp"].timestamp()
            proximity_threshold, volatility_threshold = self._get_proximity_and_volatility_thresholds(timeframe)
            min_volatility_threshold = last["close"] * volatility_threshold
            is_choppy = last["atr"] < min_volatility_threshold
            if is_choppy:
                logger.info(
                    f"{symbol} - ({timeframe.upper()}) :: "
                    + f"Market too choppy (ATR {last['atr']:.2f} < Threshold {min_volatility_threshold:.2f}). "
                    + "Skipping signal check..."
                )
            else:
                logger.info(
                    f"{symbol} - ({timeframe.upper()}) :: "
                    + f"Market is trending (ATR {last['atr']:.2f} >= Threshold {min_volatility_threshold:.2f}). "
                    + f"Checking for signals with proximity threshold: {proximity_threshold:.2f}"
                )
                # A proximity_threshold of 0 effectively disables the proximity check
                buy_signal = self._calculate_buy_signal(prev, last, proximity_threshold)
                # Sell Signal Logic
                sell_signal = self._calculate_sell_signal(prev, last, proximity_threshold)
                # RSI Anticipation Zone Logic
                rsi_state = self._get_rsi_for_anticipation_zone(last)
        ret = SignalsEvaluationResult(
            timestamp=timestamp,
            symbol=symbol,
            timeframe=timeframe,
            buy=buy_signal,
            sell=sell_signal,
            rsi_state=rsi_state,
            is_choppy=is_choppy,
        )
        return ret

    def _calculate_buy_signal(self, prev: pd.Series, last: pd.Series, proximity_threshold: float) -> bool:
        use_proximity = proximity_threshold > 0
        # Buy Signal Logic
        ema_bullish_cross = prev["ema9"] <= prev["ema21"] and last["ema9"] > last["ema21"]
        ema_bullish_proximity = use_proximity and (
            last["ema9"] > last["ema21"] and abs(last["ema9"] - last["ema21"]) / last["ema21"] < proximity_threshold
        )
        buy_signal = (ema_bullish_cross or ema_bullish_proximity) and last["macd_hist"] > 0

        return buy_signal

    def _calculate_sell_signal(self, prev: pd.Series, last: pd.Series, proximity_threshold: float) -> bool:
        use_proximity = proximity_threshold > 0
        ema_bearish_cross = prev["ema9"] >= prev["ema21"] and last["ema9"] < last["ema21"]
        ema_bearish_proximity = use_proximity and (
            last["ema9"] < last["ema21"] and abs(last["ema9"] - last["ema21"]) / last["ema21"] < proximity_threshold
        )
        sell_signal = (ema_bearish_cross or ema_bearish_proximity) and last["macd_hist"] < 0

        return sell_signal

    def _get_rsi_for_anticipation_zone(self, last: pd.Series) -> Literal["neutral", "overbought", "oversold"]:
        if last["rsi"] > self._configuration_properties.buy_sell_signals_rsi_overbought:
            rsi_state = "overbought"
        elif last["rsi"] < self._configuration_properties.buy_sell_signals_rsi_oversold:
            rsi_state = "oversold"
        else:
            rsi_state = "neutral"
        return rsi_state

    def _get_proximity_and_volatility_thresholds(self, timeframe: Literal["4h", "1h"]) -> tuple[float, float]:
        # EMA Proximity threshold
        proximity_threshold = (
            self._configuration_properties.buy_sell_signals_proximity_threshold if timeframe == "4h" else 0
        )
        # XXX: [JMSOLA] Volatility Filter Logic
        # Only proceed if the market has meaningful volatility.
        # Here, we define "meaningful" as an ATR value that is at least 0.5% of the closing price
        # for 4h period, and 0.3% of the closing price for 1h periodº
        volatility_threshold = (
            self._configuration_properties.buy_sell_signals_4h_volatility_threshold
            if timeframe == "4h"
            else self._configuration_properties.buy_sell_signals_1h_volatility_threshold
        )
        return proximity_threshold, volatility_threshold

    async def _notify_alert(
        self, telegram_chat_ids: list[str], body_message: str, *, tickers: Bit2MeTickersDto
    ) -> None:
        crypto_currency, fiat_currency = tickers.symbol.split("/")
        message = "⚡⚡ ATTENTION ⚡⚡\n\n"
        message += f"{body_message}\n"
        message += html.bold(f"🔥 {crypto_currency} current price is {tickers.close} {fiat_currency}")
        for tg_chat_id in telegram_chat_ids:
            await self._telegram_service.send_message(chat_id=tg_chat_id, text=message)
