import math
import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from itertools import product
from pathlib import Path
from typing import Any

import ccxt
import numpy as np
import pandas as pd
import pydash
from backtesting import backtesting
from joblib import Parallel, delayed
from tqdm import tqdm

from crypto_trailing_stop.commons.constants import (
    ADX_THRESHOLD_VALUES,
    BIT2ME_TAKER_FEES,
    EMA_SHORT_MID_PAIRS_AS_TUPLES,
    MAX_VOLUME_THRESHOLD_STEP_VALUE,
    MIN_VOLUME_THRESHOLD_STEP_VALUE,
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
    MAX_VOLUME_THRESHOLD_STEP_FIRST_ITERATION,
    MAX_VOLUME_THRESHOLD_VALUES_FIRST_ITERATION,
    MIN_ENTRIES_PER_WEEK,
    MIN_TRADES_FOR_STATS,
    MIN_VOLUME_THRESHOLD_STEP_FIRST_ITERATION,
    MIN_VOLUME_THRESHOLD_VALUES_FOR_FIRST_ITERATION,
)
from crypto_trailing_stop.scripts.jobs import run_single_backtest_combination
from crypto_trailing_stop.scripts.serde import BacktestResultSerde
from crypto_trailing_stop.scripts.strategy import SignalStrategy
from crypto_trailing_stop.scripts.vo import BacktestingExecutionResult, BacktestingExecutionSummary, TakeProfitFilter


class BacktestingCliService:
    def __init__(self) -> None:
        self._bit2me_remote_service = Bit2MeRemoteService()
        self._analytics_service = CryptoAnalyticsService(
            bit2me_remote_service=self._bit2me_remote_service,
            ccxt_remote_service=CcxtRemoteService(),
            buy_sell_signals_config_service=None,
        )
        self._signal_service = BuySellSignalsTaskService()
        self._serde = BacktestResultSerde()

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
        timeframe: str,
        initial_cash: float,
        downloaded_months_back: int = DEFAULT_MONTHS_BACK,
        disable_minimal_trades: bool = False,
        disable_decent_win_rate: bool = False,
        decent_win_rate: float = DECENT_WIN_RATE_THRESHOLD,
        min_profit_factor: float | None = None,
        min_sqn: float | None = None,
        tp_filter: TakeProfitFilter = "all",
        from_parquet: Path | None = None,
        df: pd.DataFrame | None = None,
        disable_progress_bar: bool = False,
        echo_fn: Callable[[str], None],
    ) -> BacktestingExecutionSummary:
        if from_parquet is None and df is None:
            raise ValueError("Either 'from_parquet' or 'df' must be provided.")
        if from_parquet is None:
            ret = self._find_out_best_parameters_in_real_time(
                symbol=symbol,
                timeframe=timeframe,
                initial_cash=initial_cash,
                downloaded_months_back=downloaded_months_back,
                disable_minimal_trades=disable_minimal_trades,
                disable_decent_win_rate=disable_decent_win_rate,
                decent_win_rate=decent_win_rate,
                min_profit_factor=min_profit_factor,
                min_sqn=min_sqn,
                tp_filter=tp_filter,
                df=df,
                disable_progress_bar=disable_progress_bar,
                echo_fn=echo_fn,
            )
        else:
            # 3.1 Load execution results from parquet file stored previously
            ret = self._find_out_best_parameters_from_parquet_file(
                from_parquet=from_parquet,
                downloaded_months_back=downloaded_months_back,
                disable_minimal_trades=disable_minimal_trades,
                disable_decent_win_rate=disable_decent_win_rate,
                decent_win_rate=decent_win_rate,
                min_profit_factor=min_profit_factor,
                min_sqn=min_sqn,
                tp_filter=tp_filter,
            )
        return ret

    def execute_backtesting(
        self,
        *,
        simulated_bs_config: BuySellSignalsConfigItem,
        initial_cash: float,
        df: pd.DataFrame,
        timeframe: str = "1h",
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
                    timeframe=timeframe,
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
                enable_tp=simulated_bs_config.enable_exit_on_take_profit,
                simulated_bs_config=simulated_bs_config,
                analytics_service=self._analytics_service,
            )
            current_execution_result = self._to_execution_result(
                simulated_bs_config, initial_cash, stats, timeframe=timeframe
            )
            return current_execution_result, bt, stats
        finally:
            backtesting._tqdm = original_backtesting_tqdm

    def _find_out_best_parameters_in_real_time(
        self,
        *,
        symbol: str,
        timeframe: str,
        initial_cash: float,
        downloaded_months_back: int = DEFAULT_MONTHS_BACK,
        disable_minimal_trades: bool = False,
        disable_decent_win_rate: bool = False,
        decent_win_rate: float = DECENT_WIN_RATE_THRESHOLD,
        min_profit_factor: float | None = None,
        min_sqn: float | None = None,
        tp_filter: TakeProfitFilter = "all",
        df: pd.DataFrame | None = None,
        disable_progress_bar: bool = False,
        echo_fn: Callable[[str], None],
    ):
        echo_fn("🍵 Starting first run with bigger volume ranges...")
        # 2.1 Run first iteration for backtesting in order to find out best candidates
        first_executions_results = self._apply_cartesian_production_execution(
            symbol=symbol,
            initial_cash=initial_cash,
            ema_short_mid_pairs_as_tuples=EMA_SHORT_MID_PAIRS_AS_TUPLES,
            buy_min_volume_threshold_values=MIN_VOLUME_THRESHOLD_VALUES_FOR_FIRST_ITERATION,
            buy_max_volume_threshold_values=MAX_VOLUME_THRESHOLD_VALUES_FIRST_ITERATION,
            sell_min_volume_threshold_values=MIN_VOLUME_THRESHOLD_VALUES_FOR_FIRST_ITERATION,
            tp_filter=tp_filter,
            disable_progress_bar=disable_progress_bar,
            df=df,
            timeframe=timeframe,
            # FIXME: Check if would make sense to apply heuristics or not
            apply_heuristics=False,
            echo_fn=echo_fn,
        )
        # 2.2 Store the all execution results in a parquet file
        self._save_executions_results_in_parquet_file(
            symbol, timeframe, tp_filter, first_executions_results, suffix="first_run"
        )
        # 2.3 Get first Execution Result Summary
        first_execution_result_summary: BacktestingExecutionSummary = self._get_backtesting_result_summary(
            downloaded_months_back=downloaded_months_back,
            disable_minimal_trades=True,
            disable_decent_win_rate=True,
            decent_win_rate=50.0,  # First execution aims to get at least one result!
            min_profit_factor=None,
            min_sqn=None,
            executions_results=first_executions_results,
        )
        echo_fn("🍵 Calculating refinement parameters...")
        (
            best_emas,
            buy_min_volume_threshold_values_second_iteration,
            buy_max_volume_threshold_values_second_iteration,
            sell_min_volume_threshold_values_second_iteration,
        ) = self._calculate_parameter_refinement(first_execution_result_summary)
        echo_fn("--- 🍵 Refinement parameters ---")
        echo_fn(f"Best EMAs:                      {str(best_emas)}")
        echo_fn(f"Buy Min Volume Thresholds:      {str(buy_min_volume_threshold_values_second_iteration)}")
        echo_fn(f"Buy Max Volume Thresholds:      {str(buy_max_volume_threshold_values_second_iteration)}")
        echo_fn(f"Sell Min Volume Thresholds:     {str(sell_min_volume_threshold_values_second_iteration)}")
        echo_fn("-----------------------------")
        echo_fn("🍵 Running second iteration with refined parameters...")
        # 2.4 Run second iteration with refinmement
        first_executions_results = self._apply_cartesian_production_execution(
            symbol=symbol,
            initial_cash=initial_cash,
            ema_short_mid_pairs_as_tuples=best_emas,
            buy_min_volume_threshold_values=buy_min_volume_threshold_values_second_iteration,
            buy_max_volume_threshold_values=buy_max_volume_threshold_values_second_iteration,
            sell_min_volume_threshold_values=sell_min_volume_threshold_values_second_iteration,
            tp_filter=tp_filter,
            disable_progress_bar=disable_progress_bar,
            df=df,
            timeframe=timeframe,
            # FIXME: Check if would make sense to apply heuristics or not
            apply_heuristics=False,
            echo_fn=echo_fn,
        )
        # 2.5 Store the all execution results in a parquet file for the second run
        self._save_executions_results_in_parquet_file(
            symbol, timeframe, tp_filter, first_executions_results, suffix="second_run"
        )
        echo_fn("🍵 Done, gathering results...")
        # 2.6 Get final results
        ret: BacktestingExecutionSummary = self._get_backtesting_result_summary(
            downloaded_months_back=downloaded_months_back,
            disable_minimal_trades=disable_minimal_trades,
            disable_decent_win_rate=disable_decent_win_rate,
            decent_win_rate=decent_win_rate,
            min_profit_factor=min_profit_factor,
            min_sqn=min_sqn,
            executions_results=first_executions_results,
        )
        return ret

    def _find_out_best_parameters_from_parquet_file(
        self,
        *,
        from_parquet: Path,
        downloaded_months_back: int = DEFAULT_MONTHS_BACK,
        disable_minimal_trades: bool = False,
        disable_decent_win_rate: bool = False,
        decent_win_rate: float = DECENT_WIN_RATE_THRESHOLD,
        min_profit_factor: float | None = None,
        min_sqn: float | None = None,
        tp_filter: TakeProfitFilter = "all",
    ):
        executions_results = self._serde.load(from_parquet)
        # 3.2 Filter results based on cli parameters
        if tp_filter == "enabled":
            executions_results = [res for res in executions_results if res.parameters.enable_exit_on_take_profit]
        elif tp_filter == "disabled":
            executions_results = [res for res in executions_results if not res.parameters.enable_exit_on_take_profit]
        ret = self._get_backtesting_result_summary(
            downloaded_months_back=downloaded_months_back,
            disable_minimal_trades=disable_minimal_trades,
            disable_decent_win_rate=disable_decent_win_rate,
            decent_win_rate=decent_win_rate,
            min_profit_factor=min_profit_factor,
            min_sqn=min_sqn,
            executions_results=executions_results,
        )
        return ret

    def _calculate_parameter_refinement(
        self, first_execution_result_summary: BacktestingExecutionSummary
    ) -> tuple[set[tuple[int, int]], list[float], list[float], list[float]]:
        buy_min_volume_threshold_values = [
            result.parameters.buy_min_volume_threshold
            for result in first_execution_result_summary.all
            if result.parameters.enable_buy_volume_filter
        ]
        if buy_min_volume_threshold_values:
            lowest_buy_min_volume_threshold = min(buy_min_volume_threshold_values)
            highest_buy_min_volume_threshold = max(buy_min_volume_threshold_values)
            buy_min_volume_threshold_values_second_iteration = [
                round(v, ndigits=2)
                for v in np.arange(
                    lowest_buy_min_volume_threshold - MIN_VOLUME_THRESHOLD_STEP_FIRST_ITERATION
                    if (lowest_buy_min_volume_threshold - MIN_VOLUME_THRESHOLD_STEP_FIRST_ITERATION) > 0
                    else lowest_buy_min_volume_threshold,
                    highest_buy_min_volume_threshold + MIN_VOLUME_THRESHOLD_STEP_FIRST_ITERATION
                    if highest_buy_min_volume_threshold < MIN_VOLUME_THRESHOLD_VALUES_FOR_FIRST_ITERATION[-1]
                    else MIN_VOLUME_THRESHOLD_VALUES_FOR_FIRST_ITERATION[-1],
                    MIN_VOLUME_THRESHOLD_STEP_VALUE,
                ).tolist()
            ]
        else:
            buy_min_volume_threshold_values_second_iteration = []

        buy_max_volume_threshold_values = [
            result.parameters.buy_max_volume_threshold
            for result in first_execution_result_summary.all
            if result.parameters.enable_buy_volume_filter
        ]
        if buy_max_volume_threshold_values:
            lowest_buy_max_volume_threshold = min(buy_max_volume_threshold_values)
            highest_buy_max_volume_threshold = max(buy_max_volume_threshold_values)
            buy_max_volume_threshold_values_second_iteration = [
                round(v, ndigits=2)
                for v in np.arange(
                    lowest_buy_max_volume_threshold - MAX_VOLUME_THRESHOLD_STEP_FIRST_ITERATION
                    if (lowest_buy_max_volume_threshold - MAX_VOLUME_THRESHOLD_STEP_FIRST_ITERATION) > 0
                    else lowest_buy_max_volume_threshold,
                    highest_buy_max_volume_threshold + MAX_VOLUME_THRESHOLD_STEP_FIRST_ITERATION
                    if highest_buy_max_volume_threshold < MAX_VOLUME_THRESHOLD_VALUES_FIRST_ITERATION[-1]
                    else MAX_VOLUME_THRESHOLD_VALUES_FIRST_ITERATION[-1],
                    MAX_VOLUME_THRESHOLD_STEP_VALUE,
                ).tolist()
            ]
        else:
            buy_max_volume_threshold_values_second_iteration = []

        sell_min_volume_threshold_values = [
            result.parameters.sell_min_volume_threshold
            for result in first_execution_result_summary.all
            if result.parameters.enable_sell_volume_filter
        ]
        if sell_min_volume_threshold_values:
            lowest_sell_min_volume_threshold = min(sell_min_volume_threshold_values)
            highest_sell_min_volume_threshold = max(sell_min_volume_threshold_values)
            sell_min_volume_threshold_values_second_iteration = [
                round(v, ndigits=2)
                for v in np.arange(
                    lowest_sell_min_volume_threshold - MIN_VOLUME_THRESHOLD_STEP_FIRST_ITERATION
                    if (lowest_sell_min_volume_threshold - MIN_VOLUME_THRESHOLD_STEP_FIRST_ITERATION) > 0
                    else lowest_sell_min_volume_threshold,
                    highest_sell_min_volume_threshold + MIN_VOLUME_THRESHOLD_STEP_FIRST_ITERATION
                    if highest_sell_min_volume_threshold < MIN_VOLUME_THRESHOLD_VALUES_FOR_FIRST_ITERATION[-1]
                    else MIN_VOLUME_THRESHOLD_VALUES_FOR_FIRST_ITERATION[-1],
                    MIN_VOLUME_THRESHOLD_STEP_VALUE,
                ).tolist()
            ]
        else:
            sell_min_volume_threshold_values_second_iteration = []

        best_emas = {
            (result.parameters.ema_short_value, result.parameters.ema_mid_value)
            for result in first_execution_result_summary.all
        }
        return (
            best_emas,
            buy_min_volume_threshold_values_second_iteration,
            buy_max_volume_threshold_values_second_iteration,
            sell_min_volume_threshold_values_second_iteration,
        )

    def _apply_cartesian_production_execution(
        self,
        *,
        symbol: str,
        initial_cash: float,
        ema_short_mid_pairs_as_tuples: list[tuple[int, int]],
        tp_filter: TakeProfitFilter,
        buy_min_volume_threshold_values: list[float],
        buy_max_volume_threshold_values: list[float],
        sell_min_volume_threshold_values: list[float],
        disable_progress_bar: bool,
        df: pd.DataFrame,
        timeframe: str = "1h",
        apply_heuristics: bool = True,
        echo_fn: Callable[[str], None] | None = None,
    ) -> list[BacktestingExecutionResult]:
        cartesian_product = self._calculate_cartesian_product(
            symbol=symbol,
            ema_short_mid_pairs_as_tuples=ema_short_mid_pairs_as_tuples,
            buy_min_volume_threshold_values=buy_min_volume_threshold_values,
            buy_max_volume_threshold_values=buy_max_volume_threshold_values,
            sell_min_volume_threshold_values=sell_min_volume_threshold_values,
            tp_filter=tp_filter,
            apply_heuristics=apply_heuristics,
            echo_fn=echo_fn,
        )
        # Use joblib to run the backtests in parallel across all available CPU cores
        # tqdm is now wrapped around the parallel execution
        results = Parallel(n_jobs=-1)(
            delayed(run_single_backtest_combination)(params, initial_cash, df, timeframe)
            for params in (tqdm(cartesian_product) if not disable_progress_bar else cartesian_product)
        )
        # Filter out any runs that failed (they will return None)
        executions_results = [res for res in results if res is not None]
        return executions_results

    def _get_backtesting_result_summary(
        self,
        *,
        downloaded_months_back: int,
        disable_minimal_trades: bool,
        disable_decent_win_rate: bool,
        decent_win_rate: float,
        min_profit_factor: float | None,
        min_sqn: float | None,
        executions_results: list[BacktestingExecutionResult],
    ) -> BacktestingExecutionSummary:
        # 4. Filter for viable strategies to analyze
        # We only care about strategies that were profitable and had a meaningful number of trades

        # 4.1. Calculate the minimum number of trades required to consider a strategy for stats
        num_of_weeks_downloaded = downloaded_months_back * 4
        min_trades_for_stats = max(MIN_TRADES_FOR_STATS, math.ceil(num_of_weeks_downloaded * MIN_ENTRIES_PER_WEEK))
        profitable_results = [
            res
            for res in executions_results
            if res.net_profit_amount > 0
            and (disable_minimal_trades or res.number_of_trades >= min_trades_for_stats)
            and (disable_decent_win_rate or res.win_rate >= decent_win_rate)
            and (min_sqn is None or res.sqn >= min_sqn)
            and (min_profit_factor is None or res.profit_factor >= min_profit_factor)
        ]
        best_overall, highest_quality, best_profitable, best_win_rate = None, None, None, None
        if profitable_results:
            # --- Category 1: Best Overall (Profit x Win Rate x Trades) ---
            best_overall = max(
                profitable_results, key=lambda r: r.net_profit_percentage * r.win_rate * r.number_of_trades
            )
            # --- Category 2: Highest Quality (Return x Win Rate) ---
            highest_quality = max(profitable_results, key=lambda r: r.net_profit_percentage * r.win_rate)
            # --- Category 3: Best Profitable Configuration ---
            best_profitable = max(profitable_results, key=lambda r: r.net_profit_amount)
            # --- Category 4: Best Win Rate ---
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

        ret = BacktestingExecutionSummary(
            best_overall=best_overall,
            highest_quality=highest_quality,
            best_profitable=best_profitable,
            best_win_rate=best_win_rate,
        )

        return ret

    def _calculate_cartesian_product(
        self,
        *,
        symbol: str,
        ema_short_mid_pairs_as_tuples: list[tuple[int, int]],
        buy_min_volume_threshold_values: list[float],
        buy_max_volume_threshold_values: list[float],
        sell_min_volume_threshold_values: list[float],
        tp_filter: TakeProfitFilter = "all",
        apply_heuristics: bool = True,
        echo_fn: Callable[[str], None] | None = None,
    ):
        # Group SL/TP pairs by SL value to ensure we have unique SL values when TP is disabled
        sp_tp_tuples = self._get_sp_tp_tuples(tp_filter=tp_filter)

        # Adding the "No filter" option (0) to ADX thresholds
        adx_threshold_values = ADX_THRESHOLD_VALUES.copy()
        adx_threshold_values.insert(0, 0)  # Adding the "No filter" option

        # Volume thresholds combinations
        buy_volume_threshold_tuples = list(product(buy_min_volume_threshold_values, buy_max_volume_threshold_values))
        if buy_volume_threshold_tuples:
            vol_case_buy_disabled = [(False, buy_min_volume_threshold_values[0], buy_max_volume_threshold_values[0])]
            vol_case_buy_enabled = [(True, min_t, max_t) for min_t, max_t in buy_volume_threshold_tuples]
            vol_buy_cases = vol_case_buy_disabled + vol_case_buy_enabled
        else:
            vol_buy_cases = [(False, 0.00, 0.00)]

        if sell_min_volume_threshold_values:
            # Case: Sell filter OFF
            vol_case_sell_disabled = [(False, sell_min_volume_threshold_values[0])]
            vol_case_sell_enabled = [(True, min_t) for min_t in sell_min_volume_threshold_values]
            vol_sell_cases = vol_case_sell_disabled + vol_case_sell_enabled
        else:
            vol_sell_cases = [(False, 0.00)]

        # Now, create the full cartesian product considering all combinations
        full_cartesian_product = list(
            product(ema_short_mid_pairs_as_tuples, sp_tp_tuples, adx_threshold_values, vol_buy_cases, vol_sell_cases)
        )
        if echo_fn:
            echo_fn(f"FULL RAW COMBINATIONS TO TEST: {len(full_cartesian_product)}")
        # --- HEURISTIC PRUNING ---
        ret = self._convert_cartesian_product_to_config_items(
            symbol, full_cartesian_product, apply_heuristics=apply_heuristics
        )
        if echo_fn and apply_heuristics:
            echo_fn(f"  -- Discarded combinations by heuristic: {len(full_cartesian_product) - len(ret)}")
            echo_fn(f"TOTAL COMBINATIONS TO TEST: {len(ret)}")
        return ret

    def _get_sp_tp_tuples(self, *, tp_filter: TakeProfitFilter = "all") -> list[tuple[bool, float, float]]:
        sp_tp_tuples_group_by_sp = pydash.group_by(SP_TP_PAIRS_AS_TUPLES, lambda pair: pair[0])
        sp_tp_tuples_when_tp_disabled = [
            (False, *sp_tp_tuples[0]) for sp_tp_tuples in sp_tp_tuples_group_by_sp.values()
        ]
        sp_tp_tuples_when_tp_enabled = [(True, *sp_tp_tuple) for sp_tp_tuple in SP_TP_PAIRS_AS_TUPLES]
        match tp_filter:
            case "all":
                sp_tp_tuples = sp_tp_tuples_when_tp_disabled + sp_tp_tuples_when_tp_enabled
            case "enabled":
                sp_tp_tuples = sp_tp_tuples_when_tp_enabled
            case "disabled":
                sp_tp_tuples = sp_tp_tuples_when_tp_disabled
            case _:
                raise ValueError(f"Take Profit filter '{tp_filter}' value is not supported.")
        return sp_tp_tuples

    def _convert_cartesian_product_to_config_items(
        self, symbol: str, full_cartesian_product: list[tuple], *, apply_heuristics: bool = True
    ) -> list[BuySellSignalsConfigItem]:
        ret = []
        for params in full_cartesian_product:
            (
                (ema_short, ema_mid),
                (enable_exit_on_take_profit, sl_multiplier, tp_multiplier),
                adx_threshold,
                (enable_buy_volume_filter, buy_min_volume_threshold, buy_max_volume_threshold),
                (enable_sell_volume_filter, sell_min_volume_threshold),
            ) = params
            config = BuySellSignalsConfigItem(
                symbol=symbol,
                ema_short_value=ema_short,
                ema_mid_value=ema_mid,
                ema_long_value=200,
                stop_loss_atr_multiplier=sl_multiplier,
                take_profit_atr_multiplier=tp_multiplier,
                enable_adx_filter=adx_threshold > 0,
                adx_threshold=adx_threshold,
                enable_buy_volume_filter=enable_buy_volume_filter,
                buy_min_volume_threshold=buy_min_volume_threshold,
                buy_max_volume_threshold=buy_max_volume_threshold,
                enable_sell_volume_filter=enable_sell_volume_filter,
                sell_min_volume_threshold=sell_min_volume_threshold,
                enable_exit_on_take_profit=enable_exit_on_take_profit,
            )
            if not apply_heuristics or self._apply_heuristics(config):
                ret.append(config)
        return ret

    def _apply_heuristics(self, config: BuySellSignalsConfigItem) -> bool:
        # Filter out combinations that don't make sense based on heuristic rules
        # Rule 1: If ADX filter is disabled,
        # TP should not be too high (to avoid over-leveraging in non-trending markets)
        is_valid_tp_for_no_trend = (
            config.adx_threshold > 0
            or not config.enable_exit_on_take_profit
            or config.take_profit_atr_multiplier <= 4.0
        )
        # Rule 2: If ADX filter is enabled with a high threshold,
        # TP should not be too low (to ensure we capture strong trends)
        is_valid_tp_for_strong_trend = (
            config.adx_threshold < 25
            or not config.enable_exit_on_take_profit
            or config.take_profit_atr_multiplier >= 4.0
        )
        # Rule 3: Avoid overly restrictive combinations.
        # If ADX is very strict, don't also have a very strict volume filter.
        is_not_too_restrictive = not (
            config.adx_threshold >= 25 and config.enable_buy_volume_filter and config.buy_min_volume_threshold > 1.5
        )
        # Rule 4: In non-trending markets (ADX filter off), enforce volume filter to confirm moves.
        is_volume_filter_enforced_in_chop = config.adx_threshold > 0 or config.enable_buy_volume_filter
        # Rule 7: For fast EMAs (which can be noisy), enforce a confirmation filter (either ADX or Volume).
        is_fast_ema_filtered = (
            (config.ema_short_value, config.ema_mid_value) not in [(7, 18), (8, 20)]
            or config.adx_threshold > 0
            or config.enable_buy_volume_filter
        )
        match = all(
            [
                is_valid_tp_for_no_trend,
                is_valid_tp_for_strong_trend,
                is_not_too_restrictive,
                is_volume_filter_enforced_in_chop,
                is_fast_ema_filtered,
            ]
        )
        return match

    def _to_execution_result(
        self,
        simulated_bs_config: BuySellSignalsConfigItem,
        initial_cash: float,
        stats: pd.Series,
        *,
        timeframe: str = "1h",
    ) -> BacktestingExecutionResult:
        days_float = self._convert_timeframe_to_days(timeframe)
        net_profit_amount = stats["Equity Final [$]"] - initial_cash
        current_execution_result = BacktestingExecutionResult(
            parameters=simulated_bs_config,
            number_of_trades=stats["# Trades"],
            win_rate=stats["Win Rate [%]"],
            net_profit_amount=net_profit_amount,
            net_profit_percentage=stats["Return [%]"],
            avg_trade_duration_in_days=round(stats["Avg. Trade Duration"] * days_float, ndigits=2),
            max_trade_duration_in_days=round(stats["Max. Trade Duration"] * days_float, ndigits=2),
            buy_and_hold_return_percentage=stats["Buy & Hold Return [%]"],
            profit_factor=stats["Profit Factor"],
            best_trade_percentage=stats["Best Trade [%]"],
            worst_trade_percentage=stats["Worst Trade [%]"],
            avg_drawdown_percentage=round(stats["Avg. Drawdown [%]"], ndigits=2),
            max_drawdown_percentage=round(stats["Max. Drawdown [%]"], ndigits=2),
            avg_drawdown_duration_in_days=round(stats["Avg. Drawdown Duration"] * days_float, ndigits=2),
            max_drawdown_duration_in_days=round(stats["Max. Drawdown Duration"] * days_float, ndigits=2),
            sqn=stats["SQN"],
        )
        return current_execution_result

    def _save_executions_results_in_parquet_file(
        self,
        symbol: str,
        timeframe: str,
        tp_filter: TakeProfitFilter,
        results: list[BacktestingExecutionResult],
        *,
        suffix: str,
    ) -> None:
        os.makedirs("data/backtesting/raw", exist_ok=True)
        parquet_file = f"data/backtesting/raw/{symbol.replace('/', '_')}_{timeframe}_{tp_filter}_{suffix}.parquet"  # noqa: E501
        self._serde.save(results=results, filepath=parquet_file)

    def _convert_timeframe_to_days(self, timeframe: str) -> float:
        td = pd.Timedelta(timeframe)
        ret = td.total_seconds() / 86400  # 86400 seconds in a day
        return ret
