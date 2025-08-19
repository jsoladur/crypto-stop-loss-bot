from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from os import getenv
from typing import Any

import ccxt
import pandas as pd
from backtesting import Backtest
from tqdm import tqdm

from crypto_trailing_stop.commons.constants import BIT2ME_TAKER_FEES
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.infrastructure.tasks.buy_sell_signals_task_service import BuySellSignalsTaskService
from crypto_trailing_stop.scripts.constants import DEFAULT_LIMIT_DOWNLOAD_BATCHES, DEFAULT_TRADING_MARKET_CONFIG
from crypto_trailing_stop.scripts.strategy import SignalStrategy


class BacktestingCliService:
    def __init__(self) -> None:
        self._bit2me_remote_service = Bit2MeRemoteService()
        self._analytics_service = CryptoAnalyticsService(
            bit2me_remote_service=self._bit2me_remote_service,
            ccxt_remote_service=CcxtRemoteService(),
            buy_sell_signals_config_service=None,
        )
        self._signal_service = BuySellSignalsTaskService()
        self._bit2me_base_url = getenv("BIT2ME_API_BASE_URL")

    def download_backtesting_data(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
        years_back: int,
        *,
        callback_fn: Callable[[], None] = None,
        echo_fn: Callable[[str], None],
    ) -> list[list[Any]]:
        _, fiat_currency, *_ = symbol.split("/")
        interval = self._bit2me_remote_service._convert_timeframe_to_interval(timeframe)
        exchange = getattr(ccxt, exchange)()

        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=365 * years_back)
        previous_since_timestamp, since_timestamp = None, int(start_date.timestamp() * 1000)
        end_timestamp = int(end_date.timestamp() * 1000)

        markets = exchange.load_markets()
        supported_symbols = [
            market["symbol"]
            for market in markets.values()
            if market.get("active", False) and str(market["quote"]).upper() == str(fiat_currency).upper()
        ]
        if symbol not in supported_symbols:
            raise ValueError(
                f"Symbol {symbol} is not supported by exchange {exchange.id} for fiat {fiat_currency}. "
                + "Please, check other exchange (e.g. Kraken, Coinbase etc.)."
            )
        has_more_data, ret = True, []
        while (
            has_more_data
            and since_timestamp < end_timestamp
            and (previous_since_timestamp is None or previous_since_timestamp < since_timestamp)
        ):
            start_datetime = datetime.fromtimestamp(since_timestamp / 1000)
            end_datetime = start_datetime + timedelta(minutes=DEFAULT_LIMIT_DOWNLOAD_BATCHES * interval)
            echo_fn(f"📆 Dowloading candles from {start_datetime.isoformat()} to {end_datetime.isoformat()}")
            ohlcv = exchange.fetch_ohlcv(symbol, "1h", since=since_timestamp, limit=DEFAULT_LIMIT_DOWNLOAD_BATCHES)
            has_more_data = ohlcv is not None and len(ohlcv) > 0
            if has_more_data:
                ret.extend(ohlcv)
                previous_since_timestamp = since_timestamp
                since_timestamp = ohlcv[-1][0] + 1
                if callback_fn:
                    callback_fn()
        return ret

    def execute_backtesting(
        self,
        *,
        symbol: str,
        ema_short: int,
        ema_mid: int,
        ema_long: int,
        filter_adx: bool,
        adx_threshold: int,
        filter_volume: bool,
        volume_threshold: float,
        enable_tp: bool,
        sl_multiplier: float,
        tp_multiplier: float,
        initial_cash: float,
        df: pd.DataFrame,
        echo_fn: Callable[[str], None],
    ) -> tuple[Backtest, pd.Series]:
        simulated_bs_config = BuySellSignalsConfigItem(
            symbol=symbol,
            ema_short_value=ema_short,
            ema_mid_value=ema_mid,
            ema_long_value=ema_long,
            stop_loss_atr_multiplier=sl_multiplier,
            take_profit_atr_multiplier=tp_multiplier,
            filter_noise_using_adx=filter_adx,
            adx_threshold=adx_threshold,
            apply_volume_filter=filter_volume,
            volume_threshold=volume_threshold,
        )

        self._analytics_service._calculate_simple_indicators(df, simulated_bs_config)
        self._analytics_service._calculate_complex_indicators(df)

        buy_signals = []
        sell_signals = []

        echo_fn("🧠 Generating signals for each historical candle...")
        for i in tqdm(range(4, len(df))):
            window_df = df.iloc[: i + 1]
            signals = self._signal_service._check_signals(
                symbol=symbol,
                timeframe="1h",
                df=window_df,
                buy_sell_signals_config=simulated_bs_config,
                trading_market_config=DEFAULT_TRADING_MARKET_CONFIG,
            )
            buy_signals.append(signals.buy)
            sell_signals.append(signals.sell)

        df["buy_signal"] = pd.Series(buy_signals, index=df.index[4:])
        df["sell_signal"] = pd.Series(sell_signals, index=df.index[4:])
        # NEW: Add previous MACD hist for the accelerating momentum check
        df["prev_macd_hist"] = df["macd_hist"].shift(1)
        df.fillna(False, inplace=True)

        echo_fn("🚀 Running trading simulation...")
        df.rename(
            columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True
        )
        bt = Backtest(df, SignalStrategy, cash=initial_cash, commission=BIT2ME_TAKER_FEES)
        stats = bt.run(
            enable_tp=enable_tp, simulated_bs_config=simulated_bs_config, analytics_service=self._analytics_service
        )

        return bt, stats
