import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from itertools import product
from os import getenv
from typing import Any

import ccxt
import pandas as pd
from backtesting import backtesting
from joblib import Parallel, delayed
from tqdm import tqdm

from crypto_trailing_stop.commons.constants import (
    ADX_THRESHOLD_VALUES,
    BIT2ME_TAKER_FEES,
    EMA_SHORT_MID_PAIRS,
    SP_TP_PAIRS,
    VOLUME_THRESHOLD_VALUES,
)
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.infrastructure.tasks.buy_sell_signals_task_service import BuySellSignalsTaskService
from crypto_trailing_stop.scripts.constants import (
    DECENT_WIN_RATE_THRESHOLD,
    DEFAULT_LIMIT_DOWNLOAD_BATCHES,
    DEFAULT_MONTHS_BACK,
    DEFAULT_TRADING_MARKET_CONFIG,
    MIN_ENTRIES_PER_WEEK,
    MIN_TRADES_FOR_STATS,
)
from crypto_trailing_stop.scripts.jobs import run_single_backtest_combination
from crypto_trailing_stop.scripts.strategy import SignalStrategy
from crypto_trailing_stop.scripts.vo import BacktestingExecutionResult, BacktestingExecutionSummary


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
        months_back: int,
        *,
        callback_fn: Callable[[], None] = None,
        echo_fn: Callable[[str], None],
    ) -> list[list[Any]]:
        _, fiat_currency, *_ = symbol.split("/")
        interval = self._bit2me_remote_service._convert_timeframe_to_interval(timeframe)
        exchange = getattr(ccxt, exchange)()

        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=30 * months_back)
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

    def find_out_best_parameters(
        self,
        *,
        symbol: str,
        initial_cash: float,
        downloaded_months_back: int = DEFAULT_MONTHS_BACK,
        df: pd.DataFrame,
        echo_fn: Callable[[str], None],
    ) -> BacktestingExecutionSummary:
        # 1. Calculate the minimum number of trades required to consider a strategy for stats
        num_of_weeks_downloaded = downloaded_months_back * 4
        min_trades_for_stats = max(MIN_TRADES_FOR_STATS, math.ceil(num_of_weeks_downloaded * MIN_ENTRIES_PER_WEEK))
        # 2. Run backtesting for all combinations
        executions_results = self._apply_cartesian_production_execution(symbol, initial_cash, df, echo_fn)
        # 3. Filter for viable strategies to analyze
        # We only care about strategies that were profitable and had a meaningful number of trades
        profitable_results = [
            res
            for res in executions_results
            if res.net_profit_percentage > 0 and res.number_of_trades >= min_trades_for_stats
        ]
        best_profitable, best_win_rate, most_robust = None, None, None
        if profitable_results:
            # --- Category 1: Best Profitable Configuration ---
            best_profitable = max(profitable_results, key=lambda r: r.net_profit_percentage)
            # --- Category 2: Best Win Rate Configuration ---
            best_win_rate = max(profitable_results, key=lambda r: r.win_rate)
            # --- Category 3: Most Robust (High Trades + Decent Win Rate + High Profit) ---
            robust_candidates = [res for res in profitable_results if res.win_rate >= DECENT_WIN_RATE_THRESHOLD]
            if robust_candidates:
                # From the high-win-rate group, find the one with the best blend of profit and trade frequency
                # We define a score that rewards both high return and a high number of trades
                most_robust = max(robust_candidates, key=lambda r: r.net_profit_percentage * r.number_of_trades)

        ret = BacktestingExecutionSummary(
            best_profitable=best_profitable, best_win_rate=best_win_rate, most_robust=most_robust
        )
        return ret

    def execute_backtesting(
        self,
        *,
        simulated_bs_config: BuySellSignalsConfigItem,
        initial_cash: float,
        df: pd.DataFrame,
        echo_fn: Callable[[str], None] | None = None,
        use_tqdm: bool = True,
    ) -> tuple[BacktestingExecutionResult, backtesting.Backtest, pd.Series]:
        original_backtesting_tqdm = backtesting._tqdm
        try:
            self._analytics_service._calculate_simple_indicators(df, simulated_bs_config)
            self._analytics_service._calculate_complex_indicators(df)

            buy_signals = []
            sell_signals = []

            if echo_fn:
                echo_fn("🧠 Generating signals for each historical candle...")
            range_of_values = range(4, len(df))
            for i in tqdm(range_of_values) if use_tqdm else range_of_values:
                window_df = df.iloc[: i + 1]
                signals = self._signal_service._check_signals(
                    symbol=simulated_bs_config.symbol,
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

            if echo_fn:
                echo_fn("🚀 Running trading simulation...")
            df.rename(
                columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"},
                inplace=True,
            )
            bt = backtesting.Backtest(df, SignalStrategy, cash=initial_cash, commission=BIT2ME_TAKER_FEES)
            if not use_tqdm:
                backtesting._tqdm = lambda iterable=None, *args, **kwargs: iterable
            stats = bt.run(
                enable_tp=simulated_bs_config.auto_exit_atr_take_profit,
                simulated_bs_config=simulated_bs_config,
                analytics_service=self._analytics_service,
            )
            current_execution_result = self._to_execution_result(simulated_bs_config, initial_cash, stats)
            return current_execution_result, bt, stats
        finally:
            backtesting._tqdm = original_backtesting_tqdm

    def _apply_cartesian_production_execution(
        self, symbol: str, initial_cash: float, df: pd.DataFrame, echo_fn: Callable[[str], None] | None = None
    ) -> list[BacktestingExecutionResult]:
        adx_threshold_values = ADX_THRESHOLD_VALUES.copy()
        adx_threshold_values.insert(0, 0)  # Adding the "No filter" option
        volume_threshold_values = VOLUME_THRESHOLD_VALUES.copy()
        volume_threshold_values.insert(0, 0.0)  # Adding the "No

        cartesian_product = list(
            product(EMA_SHORT_MID_PAIRS, SP_TP_PAIRS, adx_threshold_values, volume_threshold_values)
        )
        if echo_fn:
            echo_fn(f"Total combinations to test: {len(cartesian_product)}")
        # Use joblib to run the backtests in parallel across all available CPU cores
        # tqdm is now wrapped around the parallel execution
        results = Parallel(n_jobs=-1)(
            delayed(run_single_backtest_combination)(params, symbol, initial_cash, df)
            for params in tqdm(cartesian_product)
        )
        # Filter out any runs that failed (they will return None)
        executions_results = [res for res in results if res is not None]
        return executions_results

    def _to_execution_result(
        self, simulated_bs_config: BuySellSignalsConfigItem, initial_cash: float, stats: pd.Series
    ) -> BacktestingExecutionResult:
        net_profit_amount = stats["Equity Final [$]"] - initial_cash
        current_execution_result = BacktestingExecutionResult(
            parameters=simulated_bs_config,
            number_of_trades=stats["# Trades"],
            win_rate=stats["Win Rate [%]"],
            net_profit_amount=net_profit_amount,
            net_profit_percentage=stats["Return [%]"],
        )
        return current_execution_result
