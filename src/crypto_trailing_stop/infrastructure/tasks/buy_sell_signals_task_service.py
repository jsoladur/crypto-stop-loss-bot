import logging
from typing import override
from crypto_trailing_stop.config import get_scheduler, get_configuration_properties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.tasks.base import AbstractTaskService
from crypto_trailing_stop.infrastructure.services.enums import PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import (
    Bit2MeRemoteService,
)
from aiogram import html
from crypto_trailing_stop.infrastructure.tasks.vo.signals_evaluation_result import (
    SignalsEvaluationResult,
)
from typing import Literal
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import (
    CcxtRemoteService,
)
from crypto_trailing_stop.infrastructure.services import (
    GlobalFlagService,
)
from crypto_trailing_stop.infrastructure.services.push_notification_service import (
    PushNotificationService,
)
from crypto_trailing_stop.commons.constants import BUY_SELL_ALERTS_TIMEFRAMES
import pandas as pd
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator

logger = logging.getLogger(__name__)


class BuySellSignalsTaskService(AbstractTaskService):
    def __init__(self):
        super().__init__()
        self._configuration_properties = get_configuration_properties()
        self._global_flag_service = GlobalFlagService()
        self._push_notification_service = PushNotificationService()
        self._bit2me_remote_service = Bit2MeRemoteService()
        self._ccxt_remote_service = CcxtRemoteService()
        self._proximity_threshold = (
            self._configuration_properties.buy_sell_signals_proximity_threshold
        )
        self._last_signal_evalutation_result_cache: dict[
            str, SignalsEvaluationResult
        ] = {}
        self._scheduler: AsyncIOScheduler = get_scheduler()
        self._scheduler.add_job(
            id=self.__class__.__name__,
            func=self.run,
            # XXX: Production ready
            # Running at minute 2, 3, 5, 7, 10 past the hour!
            trigger="cron",
            minute=[2, 3, 5, 7, 10],
            hour="*",
            # XXX: For testing purposes
            # trigger="interval",
            # seconds=self._configuration_properties.job_interval_seconds,
            coalesce=True,
        )

    @override
    async def run(self) -> None:
        is_buy_sell_signals_enabled = await self._global_flag_service.is_enabled_for(
            GlobalFlagTypeEnum.BUY_SELL_SIGNALS
        )
        if is_buy_sell_signals_enabled and (
            telegram_chat_ids
            := await self._push_notification_service.get_subscription_by_type(
                notification_type=PushNotificationTypeEnum.BUY_SELL_STRATEGY_ALERT
            )
        ):
            await self._internal_run(telegram_chat_ids)
        else:
            logger.warning(
                "[ATTENTION] Buy/Sell Signals job is DISABLED! You will not receive any alert!!"
            )

    async def _internal_run(self, telegram_chat_ids: list[int]) -> None:
        async with await self._bit2me_remote_service.get_http_client() as client:
            favourite_crypto_currencies = (
                await self._bit2me_remote_service.get_favourite_crypto_currencies(
                    client=client
                )
            )
            bit2me_account_info = await self._bit2me_remote_service.get_account_info(
                client=client
            )
            symbol_timeframe_tuples = [
                (
                    f"{crypto_currency}/{bit2me_account_info.profile.currency_code}",
                    timeframe,
                )
                for crypto_currency in favourite_crypto_currencies
                for timeframe in BUY_SELL_ALERTS_TIMEFRAMES
            ]
            for current_symbol, current_timeframe in symbol_timeframe_tuples:
                try:
                    await self._eval_and_notify_signals(
                        telegram_chat_ids,
                        symbol=current_symbol,
                        timeframe=current_timeframe,
                    )
                except Exception as e:
                    logger.error(str(e), exc_info=True)
                    await self._notify_fatal_error_via_telegram(e)

    async def _eval_and_notify_signals(
        self,
        telegram_chat_ids: list[str],
        *,
        symbol: str,
        timeframe: Literal["4h", "1h"],
    ) -> None:
        df = await self._ccxt_remote_service.fetch_ohlcv(symbol, timeframe)
        df_with_indicators = self._calculate_indicators(df)
        # Use the default, wider threshold for 4H signals
        # Use a threshold of 0 for 1H signals to disable the proximity check
        signals = self._check_signals(
            symbol,
            timeframe,
            df_with_indicators,
            proximity_threshold=self._proximity_threshold if timeframe == "4h" else 0,
        )

        if self._is_new_signals(signals):
            base_symbol = symbol.split("/")[0].strip().upper()
            # 1. Report RSI Anticipation Zones
            if signals.rsi_state != "neutral":
                icon = "📈" if signals.rsi_state == "overbought" else "📉"
                message = f"{icon} {html.bold('Anticipation Zone ' + '(' + timeframe.upper() + ')')} for {html.bold(base_symbol)} - RSI is {signals.rsi_state}!"
                await self._notify_alert(telegram_chat_ids, message)
            # 2. Report Confirmation Signals (now identical for both timeframes)
            if not signals.buy or not signals.sell:
                if signals.buy:
                    message = f"🟢 🤩{html.bold('BUY SIGNAL ' + '(' + timeframe.upper() + ')')}🤩 for {html.bold(base_symbol)}!"
                    await self._notify_alert(telegram_chat_ids, message)
                if signals.sell:
                    message = f"🔴 ⚠{html.bold('SELL SIGNAL ' + '(' + timeframe.upper() + ')')}⚠ for {html.bold(base_symbol)}!"
                    await self._notify_alert(telegram_chat_ids, message)
            if not signals.buy and not signals.sell:
                logger.info(
                    f"No new confirmation signals on the {timeframe} timeframe for {base_symbol}."
                )
        else:
            logger.info("Calculated signals were already notified previously!")

    def _is_new_signals(self, current_signals: SignalsEvaluationResult) -> bool:
        is_new_signals = (
            current_signals.cache_key not in self._last_signal_evalutation_result_cache
        )
        if not is_new_signals:
            previous_signals = self._last_signal_evalutation_result_cache[
                current_signals.cache_key
            ]
            is_new_signals = previous_signals.timestamp != current_signals.timestamp
        self._last_signal_evalutation_result_cache[current_signals.cache_key] = (
            current_signals
        )
        return is_new_signals

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Calculating indicators...")
        df["ema9"] = EMAIndicator(df["close"], window=9).ema_indicator()
        df["ema21"] = EMAIndicator(df["close"], window=21).ema_indicator()
        df["ema200"] = EMAIndicator(df["close"], window=200).ema_indicator()
        macd = MACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
        df["macd_hist"] = macd.macd_diff()
        df["rsi"] = RSIIndicator(df["close"], window=14).rsi()
        df.dropna(inplace=True)
        df.reset_index(drop=True, inplace=True)
        logger.info("Indicator calculation complete.")
        return df

    def _check_signals(
        self,
        symbol: str,
        timeframe: Literal["4h", "1h"],
        df: pd.DataFrame,
        proximity_threshold: float,
        rsi_overbought: int = 70,
        rsi_oversold: int = 30,
    ) -> SignalsEvaluationResult:
        if len(df) < 2:
            ret = SignalsEvaluationResult(buy=False, sell=False, rsi_state="neutral")
        else:
            logger.info(
                f"Checking signals for {symbol} ({timeframe.upper()}) with proximity threshold: {proximity_threshold}"
            )
            last = df.iloc[-1]
            prev = df.iloc[-2]

            # A proximity_threshold of 0 effectively disables the proximity check
            use_proximity = proximity_threshold > 0

            # Buy Signal Logic
            ema_bullish_cross = (
                prev["ema9"] <= prev["ema21"] and last["ema9"] > last["ema21"]
            )
            ema_bullish_proximity = use_proximity and (
                last["ema9"] > last["ema21"]
                and abs(last["ema9"] - last["ema21"]) / last["ema21"]
                < proximity_threshold
            )
            buy_signal = (ema_bullish_cross or ema_bullish_proximity) and last[
                "macd_hist"
            ] > 0

            # Sell Signal Logic
            ema_bearish_cross = (
                prev["ema9"] >= prev["ema21"] and last["ema9"] < last["ema21"]
            )
            ema_bearish_proximity = use_proximity and (
                last["ema9"] < last["ema21"]
                and abs(last["ema9"] - last["ema21"]) / last["ema21"]
                < proximity_threshold
            )
            sell_signal = (ema_bearish_cross or ema_bearish_proximity) and last[
                "macd_hist"
            ] < 0

            # RSI Anticipation Zone Logic
            if last["rsi"] > rsi_overbought:
                rsi_state = "overbought"
            elif last["rsi"] < rsi_oversold:
                rsi_state = "oversold"
            else:
                rsi_state = "neutral"
            ret = SignalsEvaluationResult(
                timestamp=last["timestamp"].timestamp(),
                symbol=symbol,
                timeframe=timeframe,
                buy=buy_signal,
                sell=sell_signal,
                rsi_state=rsi_state,
            )
        return ret

    async def _notify_alert(self, telegram_chat_ids: list[str], message) -> None:
        for tg_chat_id in telegram_chat_ids:
            await self._telegram_service.send_message(
                chat_id=tg_chat_id,
                text=message,
            )
