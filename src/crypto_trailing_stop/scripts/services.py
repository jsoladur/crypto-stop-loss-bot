import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from itertools import product
from os import getenv
from typing import Any

import ccxt
import pandas as pd
import pydash
from backtesting import backtesting
from joblib import Parallel, delayed
from tqdm import tqdm

from crypto_trailing_stop.commons.constants import (
    ADX_THRESHOLD_VALUES,
    BIT2ME_TAKER_FEES,
    EMA_SHORT_MID_PAIRS_AS_TUPLES,
    MAX_VOLUME_THRESHOLD_VALUES,
    MIN_VOLUME_THRESHOLD_VALUES,
    SP_TP_PAIRS_AS_TUPLES,
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
        disable_minimal_trades: bool = False,
        disable_decent_win_rate: bool = False,
        decent_win_rate: float = DECENT_WIN_RATE_THRESHOLD,
        disable_progress_bar: bool = False,
        df: pd.DataFrame,
        echo_fn: Callable[[str], None],
    ) -> BacktestingExecutionSummary:
        # 1. Calculate the minimum number of trades required to consider a strategy for stats
        num_of_weeks_downloaded = downloaded_months_back * 4
        min_trades_for_stats = max(MIN_TRADES_FOR_STATS, math.ceil(num_of_weeks_downloaded * MIN_ENTRIES_PER_WEEK))
        # 2. Run backtesting for all combinations
        executions_results = self._apply_cartesian_production_execution(
            symbol, initial_cash, disable_progress_bar, df, echo_fn
        )
        # 3. Filter for viable strategies to analyze
        # We only care about strategies that were profitable and had a meaningful number of trades
        profitable_results = [
            res
            for res in executions_results
            if res.net_profit_amount > 0
            and (disable_minimal_trades or res.number_of_trades >= min_trades_for_stats)
            and (disable_decent_win_rate or res.win_rate >= decent_win_rate)
        ]
        best_profitable, best_win_rate, highest_quality, most_robust = None, None, None, None
        if profitable_results:
            # --- Category 1: Best Profitable Configuration ---
            best_profitable = max(profitable_results, key=lambda r: r.net_profit_amount)
            # --- Category 2: Best Win Rate ---
            # First, find the maximum win rate that was achieved
            max_win_rate = max(p.win_rate for p in profitable_results)
            # Create a group of "elite" candidates with a win rate close to the maximum
            # (e.g., all strategies within 5 percentage points of the best result)
            elite_win_rate_candidates = [res for res in profitable_results if res.win_rate >= (max_win_rate - 5.0)]
            # From that elite group, pick the one with the highest NET RETURN.
            if elite_win_rate_candidates:
                best_win_rate = max(elite_win_rate_candidates, key=lambda r: r.net_profit_amount)
            else:  # Fallback in case the list is empty (should not happen)
                best_win_rate = max(profitable_results, key=lambda r: r.win_rate)
            # --- Category 3: Highest Quality (Return x Win Rate) ---
            highest_quality = max(profitable_results, key=lambda r: r.net_profit_percentage * r.win_rate)
            # --- Category 4: Most Robust (High Trades + Decent Win Rate + High Profit) ---
            most_robust = max(profitable_results, key=lambda r: r.net_profit_percentage * r.number_of_trades)

        ret = BacktestingExecutionSummary(
            best_profitable=best_profitable,
            best_win_rate=best_win_rate,
            highest_quality=highest_quality,
            most_robust=most_robust,
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
        self,
        symbol: str,
        initial_cash: float,
        disable_progress_bar: bool,
        df: pd.DataFrame,
        echo_fn: Callable[[str], None] | None = None,
    ) -> list[BacktestingExecutionResult]:
        cartesian_product = self._calculate_cartesian_product(echo_fn=echo_fn)
        # Use joblib to run the backtests in parallel across all available CPU cores
        # tqdm is now wrapped around the parallel execution
        results = Parallel(n_jobs=-1)(
            delayed(run_single_backtest_combination)(params, symbol, initial_cash, df)
            for params in (tqdm(cartesian_product) if not disable_progress_bar else cartesian_product)
        )
        # Filter out any runs that failed (they will return None)
        executions_results = [res for res in results if res is not None]
        return executions_results

    def _calculate_cartesian_product(self, *, echo_fn: Callable[[str], None] | None = None):
        # Adding the "No filter" option (0) to ADX thresholds
        adx_threshold_values = ADX_THRESHOLD_VALUES.copy()
        adx_threshold_values.insert(0, 0)  # Adding the "No filter" option

        # Group SL/TP pairs by SL value to ensure we have unique SL values when TP is disabled
        sp_tp_tuples_group_by_sp = pydash.group_by(SP_TP_PAIRS_AS_TUPLES, lambda pair: pair[0])
        sp_tp_tuples_when_tp_disabled = [
            (False, *sp_tp_tuples[0]) for sp_tp_tuples in sp_tp_tuples_group_by_sp.values()
        ]
        sp_tp_tuples_when_tp_enabled = [(True, *sp_tp_tuple) for sp_tp_tuple in SP_TP_PAIRS_AS_TUPLES]
        valid_sp_tp_tuples = sp_tp_tuples_when_tp_disabled + sp_tp_tuples_when_tp_enabled

        # Volume thresholds combinations
        volume_threshold_tuples_when_filter_volume_disabled = [
            (False, MIN_VOLUME_THRESHOLD_VALUES[0], MAX_VOLUME_THRESHOLD_VALUES[0])
        ]
        volume_threshold_tuples = list(product(MIN_VOLUME_THRESHOLD_VALUES.copy(), MAX_VOLUME_THRESHOLD_VALUES.copy()))
        volume_threshold_tuples_when_filter_volume_enabled = [
            (True, *vol_threshold_tuple) for vol_threshold_tuple in volume_threshold_tuples
        ]
        # Final list of all valid Volume Filter combinations
        valid_volume_threshold_tuples = (
            volume_threshold_tuples_when_filter_volume_disabled + volume_threshold_tuples_when_filter_volume_enabled
        )
        # Now, create the full cartesian product considering all combinations
        full_cartesian_product = list(
            product(
                EMA_SHORT_MID_PAIRS_AS_TUPLES, valid_sp_tp_tuples, adx_threshold_values, valid_volume_threshold_tuples
            )
        )
        if echo_fn:
            echo_fn(f"Full raw combinations to test: {len(full_cartesian_product)}")
        ret = []
        # --- HEURISTIC PRUNING ---
        for params in full_cartesian_product:
            (_, (auto_exit_atr_take_profit, _, tp_multiplier), adx_threshold, _) = params
            # Filter out combinations that don't make sense based on heuristic rules
            # 1. If ADX filter is disabled, TP should not be too high (to avoid over-leveraging in non-trending markets)
            is_valid_tp_for_no_trend = adx_threshold > 0 or not auto_exit_atr_take_profit or tp_multiplier <= 4.0
            # 2. If ADX filter is enabled with a high threshold,
            # TP should not be too low (to ensure we capture strong trends)
            is_valid_tp_for_strong_trend = adx_threshold < 25 or not auto_exit_atr_take_profit or tp_multiplier >= 4.0
            if is_valid_tp_for_no_trend and is_valid_tp_for_strong_trend:
                ret.append(params)
        if echo_fn:
            echo_fn(f"Total combinations to test: {len(ret)}")
            echo_fn(f"  -- Discarded combinations by heuristic: {len(full_cartesian_product) - len(ret)}")
        return ret

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
