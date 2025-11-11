import math
import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from itertools import product
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import ccxt
import numpy as np
import pandas as pd
import pydash
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backtesting import backtesting
from joblib import Parallel, delayed
from tqdm import tqdm

from crypto_trailing_stop.commons.constants import (
    ADX_THRESHOLD_VALUES,
    BIT2ME_TAKER_FEES,
    EMA_SHORT_MID_PAIRS_AS_TUPLES,
    MAX_VOLUME_THRESHOLD_STEP_VALUE,
    MEXC_TAKER_FEES,
    MIN_VOLUME_THRESHOLD_STEP_VALUE,
    SP_TP_PAIRS_AS_TUPLES,
)
from crypto_trailing_stop.config.configuration_properties import ConfigurationProperties
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.infrastructure.tasks.buy_sell_signals_task_service import BuySellSignalsTaskService
from crypto_trailing_stop.scripts.constants import (
    DECENT_WIN_RATE_THRESHOLD,
    DEFAULT_LIMIT_DOWNLOAD_BATCHES,
    DEFAULT_MONTHS_BACK,
    DEFAULT_TRADING_MARKET_CONFIG,
    ITERATE_OVER_EXEC_RESULTS_MAX_ATTEMPS,
    MAX_VOLUME_THRESHOLD_STEP_FIRST_ITERATION,
    MAX_VOLUME_THRESHOLD_VALUES_FIRST_ITERATION,
    MIN_ENTRIES_PER_WEEK,
    MIN_TRADES_FOR_DEFAULT_MONTHS_BACK,
    MIN_VOLUME_THRESHOLD_STEP_FIRST_ITERATION,
    MIN_VOLUME_THRESHOLD_VALUES_FOR_FIRST_ITERATION,
)
from crypto_trailing_stop.scripts.jobs import run_single_backtest_combination
from crypto_trailing_stop.scripts.serde import BacktestResultSerde
from crypto_trailing_stop.scripts.strategy import SignalStrategy
from crypto_trailing_stop.scripts.vo import (
    BacktestingExecutionResult,
    BacktestingInOutOfSampleExecutionResult,
    BacktestingInOutOfSampleRanking,
    BacktestingOutcomes,
    ParametersRefinementResult,
    TakeProfitFilter,
)


class BacktestingCliService:
    def __init__(self) -> None:
        ccxt_remote_service = CcxtRemoteService(configuration_properties=SimpleNamespace(operating_exchange="mexc"))
        self._analytics_service = CryptoAnalyticsService(
            operating_exchange_service=None,
            ccxt_remote_service=ccxt_remote_service,
            favourite_crypto_currency_service=None,
            buy_sell_signals_config_service=None,
        )
        self._signal_service = BuySellSignalsTaskService(
            configuration_properties=ConfigurationProperties(),
            operating_exchange_service=None,
            push_notification_service=None,
            telegram_service=None,
            event_emitter=None,
            scheduler=AsyncIOScheduler(),
            ccxt_remote_service=ccxt_remote_service,
            global_flag_service=None,
            favourite_crypto_currency_service=None,
            crypto_analytics_service=None,
            auto_buy_trader_config_service=None,
        )
        self._serde = BacktestResultSerde()

    def download_backtesting_data(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
        months_back: int,
        months_offset: int,
        *,
        callback_fn: Callable[[], None] = None,
        echo_fn: Callable[[str], None],
    ) -> list[list[Any]]:
        _, fiat_currency, *_ = symbol.split("/")
        interval = self._convert_timeframe_to_interval(timeframe)
        exchange = getattr(ccxt, exchange)()

        end_date = datetime.now(UTC)
        if months_offset > 0:
            end_date = end_date - timedelta(days=30 * months_offset)
        start_date = end_date - timedelta(days=30 * months_back)
        previous_since_timestamp, since_timestamp = None, int(start_date.timestamp() * 1000)
        end_timestamp = int(end_date.timestamp() * 1000)

        markets = exchange.load_markets()
        supported_symbols = [
            market["symbol"]
            for market in markets.values()
            if (market.get("active", False) or market.get("spot", False))
            and str(market["quote"]).upper() == str(fiat_currency).upper()
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
        exchange: str,
        timeframe: str,
        initial_cash: float,
        disable_minimal_trades: bool = False,
        disable_decent_win_rate: bool = False,
        decent_win_rate: float = DECENT_WIN_RATE_THRESHOLD,
        min_profit_factor: float | None = None,
        min_sqn: float | None = None,
        tp_filter: TakeProfitFilter = "all",
        from_parquet: Path | None = None,
        in_sample_df: pd.DataFrame | None = None,
        out_of_sample_df: pd.DataFrame | None = None,
        disable_progress_bar: bool = False,
        echo_fn: Callable[[str], None],
    ) -> tuple[BacktestingInOutOfSampleRanking, BacktestingInOutOfSampleRanking]:
        if from_parquet is None and (in_sample_df is None or out_of_sample_df is None):
            raise ValueError("Either 'from_parquet' or both 'in_sample_df' and 'out_of_sample_df' must be provided.")
        if from_parquet is None:
            ret = self._find_out_in_sample_best_parameters_in_real_time(
                symbol=symbol,
                exchange=exchange,
                timeframe=timeframe,
                initial_cash=initial_cash,
                disable_minimal_trades=disable_minimal_trades,
                disable_decent_win_rate=disable_decent_win_rate,
                decent_win_rate=decent_win_rate,
                min_profit_factor=min_profit_factor,
                min_sqn=min_sqn,
                tp_filter=tp_filter,
                df=in_sample_df,
                disable_progress_bar=disable_progress_bar,
                echo_fn=echo_fn,
            )
        else:
            # 3.1 Load execution results from parquet file stored previously
            ret = self._find_out_in_sample_best_parameters_from_parquet_file(
                from_parquet=from_parquet,
                disable_minimal_trades=disable_minimal_trades,
                disable_decent_win_rate=disable_decent_win_rate,
                decent_win_rate=decent_win_rate,
                min_profit_factor=min_profit_factor,
                min_sqn=min_sqn,
                tp_filter=tp_filter,
            )

        echo_fn("🍵 Applying OUT OF SAMPLE validation...")
        for current in tqdm(ret.all) if not disable_progress_bar else ret.all:
            out_of_sample_result, *_ = self.execute_backtesting(
                exchange=exchange,
                simulated_bs_config=current.parameters,
                initial_cash=initial_cash,
                df=out_of_sample_df.copy(),
                timeframe=timeframe,
                use_tqdm=False,
            )
            current.out_of_sample_outcomes = out_of_sample_result.outcomes
        return ret

    def execute_backtesting(
        self,
        *,
        exchange: str,
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
            bt = backtesting.Backtest(
                df,
                SignalStrategy,
                cash=initial_cash,
                commission=MEXC_TAKER_FEES if exchange == "mexc" else BIT2ME_TAKER_FEES,
            )
            if not use_tqdm:
                backtesting._tqdm = lambda iterable=None, *args, **kwargs: iterable
            stats = bt.run(simulated_bs_config=simulated_bs_config, analytics_service=self._analytics_service)
            current_execution_result = self._to_execution_result(
                simulated_bs_config, initial_cash, stats, timeframe=timeframe
            )
            return current_execution_result, bt, stats
        finally:
            backtesting._tqdm = original_backtesting_tqdm

    def _find_out_in_sample_best_parameters_in_real_time(
        self,
        *,
        symbol: str,
        exchange: str,
        timeframe: str,
        initial_cash: float,
        disable_minimal_trades: bool = False,
        disable_decent_win_rate: bool = False,
        decent_win_rate: float = DECENT_WIN_RATE_THRESHOLD,
        min_profit_factor: float | None = None,
        min_sqn: float | None = None,
        tp_filter: TakeProfitFilter = "all",
        df: pd.DataFrame | None = None,
        disable_progress_bar: bool = False,
        echo_fn: Callable[[str], None],
    ) -> BacktestingInOutOfSampleRanking:
        echo_fn("🍵 Starting research with first run IN SAMPLE data with bigger volume ranges...")
        first_in_sample_executions_results = self._apply_cartesian_production_execution(
            symbol=symbol,
            exchange=exchange,
            initial_cash=initial_cash,
            ema_short_mid_pairs_as_tuples=EMA_SHORT_MID_PAIRS_AS_TUPLES,
            buy_min_volume_threshold_values=MIN_VOLUME_THRESHOLD_VALUES_FOR_FIRST_ITERATION,
            buy_max_volume_threshold_values=MAX_VOLUME_THRESHOLD_VALUES_FIRST_ITERATION,
            sell_min_volume_threshold_values=MIN_VOLUME_THRESHOLD_VALUES_FOR_FIRST_ITERATION,
            tp_filter=tp_filter,
            disable_progress_bar=disable_progress_bar,
            df=df,
            timeframe=timeframe,
            echo_fn=echo_fn,
        )
        # 2.2 Store all execution results in a parquet file
        self._save_executions_results_in_parquet_file(
            symbol, timeframe, tp_filter, first_in_sample_executions_results, suffix="in_sample_first_run"
        )
        first_execution_result_ranking = self._iter_over_executions_results_to_get_final_results(
            disable_minimal_trades=disable_minimal_trades,
            disable_decent_win_rate=disable_decent_win_rate,
            decent_win_rate=decent_win_rate,
            min_profit_factor=min_profit_factor,
            min_sqn=min_sqn,
            executions_results=first_in_sample_executions_results,
        )
        if len(first_execution_result_ranking.all) <= 0:
            first_execution_result_ranking = self._iter_over_executions_results_to_get_final_results(
                disable_minimal_trades=True,
                disable_decent_win_rate=True,
                min_profit_factor=None,
                min_sqn=None,
                executions_results=first_in_sample_executions_results,
            )
        echo_fn("🍵 Calculating refinement parameters...")
        parameters_refinement_result: list[ParametersRefinementResult] = self._calculate_parameter_refinement(
            first_execution_result_ranking
        )
        echo_fn("--- 🍵 Refinement parameters ---")
        for current in parameters_refinement_result:
            echo_fn(f"* EMAs:                      {str((current.ema_short, current.ema_mid))}")
            echo_fn(f"---- Buy Min Volume Thresholds:      {str(current.buy_min_volume_threshold_values)}")
            echo_fn(f"---- Buy Max Volume Thresholds:      {str(current.buy_max_volume_threshold_values)}")
            echo_fn(f"---- Sell Min Volume Thresholds:     {str(current.sell_min_volume_threshold_values)}")
            echo_fn(f"---- SL/TP tuples:     {str(current.sp_tp_tuples)}")
            echo_fn("-----------------------------")
        echo_fn("=============================")
        # 2.4 Run second iteration with refinmement
        second_full_cartesian_product: list[BuySellSignalsConfigItem] = []
        for current in parameters_refinement_result:
            current_cartesian_product = self._calculate_cartesian_product(
                symbol=symbol,
                ema_short_mid_pairs_as_tuples=[(current.ema_short, current.ema_mid)],
                buy_min_volume_threshold_values=current.buy_min_volume_threshold_values,
                buy_max_volume_threshold_values=current.buy_max_volume_threshold_values,
                sell_min_volume_threshold_values=current.sell_min_volume_threshold_values,
                sp_tp_tuples=current.sp_tp_tuples,
                tp_filter=tp_filter,
                echo_fn=echo_fn,
            )
            second_full_cartesian_product.extend(current_cartesian_product)
        echo_fn("🍵 Running second IN-SAMPLE iteration with refined parameters...")
        second_executions_results = self._exec_joblib_execution_by_cartesian_product(
            exchange=exchange,
            initial_cash=initial_cash,
            disable_progress_bar=disable_progress_bar,
            df=df,
            timeframe=timeframe,
            cartesian_product=second_full_cartesian_product,
        )
        # 2.5 Store the all execution results in a parquet file for the second run
        self._save_executions_results_in_parquet_file(
            symbol, timeframe, tp_filter, second_executions_results, suffix="second_run"
        )
        echo_fn("🍵 Done, gathering results...")
        # 2.6 Get final results
        ret = self._iter_over_executions_results_to_get_final_results(
            disable_minimal_trades=disable_minimal_trades,
            disable_decent_win_rate=disable_decent_win_rate,
            decent_win_rate=decent_win_rate,
            min_profit_factor=min_profit_factor,
            min_sqn=min_sqn,
            executions_results=second_executions_results,
        )
        return ret

    def _find_out_in_sample_best_parameters_from_parquet_file(
        self,
        *,
        from_parquet: Path,
        disable_minimal_trades: bool = False,
        disable_decent_win_rate: bool = False,
        decent_win_rate: float = DECENT_WIN_RATE_THRESHOLD,
        min_profit_factor: float | None = None,
        min_sqn: float | None = None,
        tp_filter: TakeProfitFilter = "all",
    ) -> BacktestingInOutOfSampleRanking:
        executions_results = self._serde.load(from_parquet)
        # 3.2 Filter results based on cli parameters
        if tp_filter == "enabled":
            executions_results = [res for res in executions_results if res.parameters.enable_exit_on_take_profit]
        elif tp_filter == "disabled":
            executions_results = [res for res in executions_results if not res.parameters.enable_exit_on_take_profit]
        ret = self._iter_over_executions_results_to_get_final_results(
            disable_minimal_trades=disable_minimal_trades,
            disable_decent_win_rate=disable_decent_win_rate,
            decent_win_rate=decent_win_rate,
            min_profit_factor=min_profit_factor,
            min_sqn=min_sqn,
            executions_results=executions_results,
        )
        return ret

    def _calculate_parameter_refinement(
        self, execution_ranking: BacktestingInOutOfSampleRanking
    ) -> list[ParametersRefinementResult]:
        parameters_refinement_result_dict: dict[tuple[int, int], ParametersRefinementResult] = {}
        for result in execution_ranking.all:
            ema_short_and_mid_values = (result.parameters.ema_short_value, result.parameters.ema_mid_value)
            sp_tp_tuple = (
                result.parameters.enable_exit_on_take_profit,
                result.parameters.stop_loss_atr_multiplier,
                result.parameters.take_profit_atr_multiplier,
            )
            parameters_refinement = parameters_refinement_result_dict.setdefault(
                ema_short_and_mid_values,
                ParametersRefinementResult(
                    ema_short=result.parameters.ema_short_value, ema_mid=result.parameters.ema_mid_value
                ),
            )
            if result.parameters.enable_buy_volume_filter:
                parameters_refinement.buy_min_volume_threshold_values.append(result.parameters.buy_min_volume_threshold)
                parameters_refinement.buy_max_volume_threshold_values.append(result.parameters.buy_max_volume_threshold)
            if result.parameters.enable_sell_volume_filter:
                parameters_refinement.sell_min_volume_threshold_values.append(
                    result.parameters.sell_min_volume_threshold
                )
            if sp_tp_tuple not in parameters_refinement.sp_tp_tuples:
                parameters_refinement.sp_tp_tuples.append(sp_tp_tuple)

        ret: list[ParametersRefinementResult] = []
        for current in parameters_refinement_result_dict.values():
            if current.buy_min_volume_threshold_values:
                lowest_buy_min_volume_threshold = min(current.buy_min_volume_threshold_values)
                highest_buy_min_volume_threshold = max(current.buy_min_volume_threshold_values)
                current.buy_min_volume_threshold_values = sorted(
                    list(
                        {
                            round(v, ndigits=2)
                            for v in np.arange(
                                lowest_buy_min_volume_threshold
                                - MIN_VOLUME_THRESHOLD_STEP_FIRST_ITERATION
                                + MIN_VOLUME_THRESHOLD_STEP_VALUE
                                if (lowest_buy_min_volume_threshold - MIN_VOLUME_THRESHOLD_STEP_FIRST_ITERATION) >= 0
                                else lowest_buy_min_volume_threshold,
                                highest_buy_min_volume_threshold + MIN_VOLUME_THRESHOLD_STEP_FIRST_ITERATION
                                if highest_buy_min_volume_threshold
                                < MIN_VOLUME_THRESHOLD_VALUES_FOR_FIRST_ITERATION[-1]
                                else MIN_VOLUME_THRESHOLD_VALUES_FOR_FIRST_ITERATION[-1],
                                MIN_VOLUME_THRESHOLD_STEP_VALUE,
                            ).tolist()
                        }
                    )
                )
            else:
                current.buy_min_volume_threshold_values = []
            if current.buy_max_volume_threshold_values:
                lowest_buy_max_volume_threshold = min(current.buy_max_volume_threshold_values)
                highest_buy_max_volume_threshold = max(current.buy_max_volume_threshold_values)
                current.buy_max_volume_threshold_values = sorted(
                    list(
                        {
                            round(v, ndigits=2)
                            for v in np.arange(
                                lowest_buy_max_volume_threshold
                                - MAX_VOLUME_THRESHOLD_STEP_FIRST_ITERATION
                                + MAX_VOLUME_THRESHOLD_STEP_VALUE
                                if (lowest_buy_max_volume_threshold - MAX_VOLUME_THRESHOLD_STEP_FIRST_ITERATION) >= 0
                                else lowest_buy_max_volume_threshold,
                                highest_buy_max_volume_threshold + MAX_VOLUME_THRESHOLD_STEP_FIRST_ITERATION
                                if highest_buy_max_volume_threshold < MAX_VOLUME_THRESHOLD_VALUES_FIRST_ITERATION[-1]
                                else MAX_VOLUME_THRESHOLD_VALUES_FIRST_ITERATION[-1],
                                MAX_VOLUME_THRESHOLD_STEP_VALUE,
                            ).tolist()
                        }
                    )
                )
            else:
                current.buy_max_volume_threshold_values = []
            if current.sell_min_volume_threshold_values:
                lowest_sell_min_volume_threshold = min(current.sell_min_volume_threshold_values)
                highest_sell_min_volume_threshold = max(current.sell_min_volume_threshold_values)
                current.sell_min_volume_threshold_values = sorted(
                    list(
                        {
                            round(v, ndigits=2)
                            for v in np.arange(
                                lowest_sell_min_volume_threshold
                                - MIN_VOLUME_THRESHOLD_STEP_FIRST_ITERATION
                                + MIN_VOLUME_THRESHOLD_STEP_VALUE
                                if (lowest_sell_min_volume_threshold - MIN_VOLUME_THRESHOLD_STEP_FIRST_ITERATION) >= 0
                                else lowest_sell_min_volume_threshold,
                                highest_sell_min_volume_threshold + MIN_VOLUME_THRESHOLD_STEP_FIRST_ITERATION
                                if highest_sell_min_volume_threshold
                                < MIN_VOLUME_THRESHOLD_VALUES_FOR_FIRST_ITERATION[-1]
                                else MIN_VOLUME_THRESHOLD_VALUES_FOR_FIRST_ITERATION[-1],
                                MIN_VOLUME_THRESHOLD_STEP_VALUE,
                            ).tolist()
                        }
                    )
                )
            else:
                current.sell_min_volume_threshold_values = []
            ret.append(current)
        return ret

    def _apply_cartesian_production_execution(
        self,
        *,
        symbol: str,
        exchange: str,
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
        ret = self._exec_joblib_execution_by_cartesian_product(
            exchange=exchange,
            initial_cash=initial_cash,
            disable_progress_bar=disable_progress_bar,
            df=df,
            timeframe=timeframe,
            cartesian_product=cartesian_product,
        )
        return ret

    def _exec_joblib_execution_by_cartesian_product(
        self,
        *,
        exchange: str,
        initial_cash: float,
        disable_progress_bar: bool,
        df: pd.DataFrame,
        timeframe: str,
        cartesian_product: list[BuySellSignalsConfigItem],
    ) -> list[BacktestingExecutionResult]:
        results = Parallel(n_jobs=-1)(
            delayed(run_single_backtest_combination)(exchange, params, initial_cash, df, timeframe)
            for params in (tqdm(cartesian_product) if not disable_progress_bar else cartesian_product)
        )
        # Filter out any runs that failed (they will return None)
        executions_results = [res for res in results if res is not None]
        return executions_results

    def _iter_over_executions_results_to_get_final_results(
        self,
        *,
        disable_minimal_trades: bool = False,
        disable_decent_win_rate: bool = False,
        decent_win_rate: float = DECENT_WIN_RATE_THRESHOLD,
        min_profit_factor: float | None = None,
        min_sqn: float | None = None,
        executions_results: list[BacktestingExecutionResult],
    ) -> BacktestingInOutOfSampleRanking:
        ret: BacktestingInOutOfSampleRanking = None
        # Try first to iterative over decent win rate
        attemps = 0
        current_decent_win_rate = None
        while attemps < ITERATE_OVER_EXEC_RESULTS_MAX_ATTEMPS and (ret is None or len(ret.all) <= 0):
            attemps += 1
            current_decent_win_rate = (
                decent_win_rate if current_decent_win_rate is None else (current_decent_win_rate - 1)
            )
            current_decent_win_rate = (
                round(current_decent_win_rate, ndigits=2) if current_decent_win_rate is not None else None
            )
            ret = self._get_backtesting_ranking(
                disable_minimal_trades=disable_minimal_trades,
                disable_decent_win_rate=disable_decent_win_rate,
                decent_win_rate=current_decent_win_rate
                if current_decent_win_rate is not None and current_decent_win_rate > 0
                else None,
                min_profit_factor=min_profit_factor,
                min_sqn=min_sqn,
                executions_results=executions_results,
            )

        # Iterate over min SQN
        attemps = 0
        current_min_sqn = None
        while attemps < ITERATE_OVER_EXEC_RESULTS_MAX_ATTEMPS and (ret is None or len(ret.all) <= 0):
            attemps += 1
            current_min_sqn = min_sqn if current_min_sqn is None else (current_min_sqn - 0.1)
            current_min_sqn = round(current_min_sqn, ndigits=2) if current_min_sqn is not None else None
            ret = self._get_backtesting_ranking(
                disable_minimal_trades=disable_minimal_trades,
                disable_decent_win_rate=disable_decent_win_rate,
                decent_win_rate=decent_win_rate,
                min_profit_factor=min_profit_factor,
                min_sqn=current_min_sqn if current_min_sqn is not None and current_min_sqn > 0 else None,
                executions_results=executions_results,
            )
        # Iterate over min profit factor
        attemps = 0
        current_min_profit = None
        while attemps < ITERATE_OVER_EXEC_RESULTS_MAX_ATTEMPS and (ret is None or len(ret.all) <= 0):
            attemps += 1
            current_min_profit = min_profit_factor if current_min_profit is None else (current_min_profit - 0.1)
            current_min_profit = round(current_min_profit, ndigits=2) if current_min_profit is not None else None
            ret = self._get_backtesting_ranking(
                disable_minimal_trades=disable_minimal_trades,
                disable_decent_win_rate=disable_decent_win_rate,
                decent_win_rate=decent_win_rate,
                min_profit_factor=current_min_profit
                if current_min_profit is not None and current_min_profit > 0
                else None,
                min_sqn=None,
                executions_results=executions_results,
            )
        # Iterate over decent win rate second time, without min profit factor and min_sqn
        attemps = 0
        current_decent_win_rate = None
        while attemps < ITERATE_OVER_EXEC_RESULTS_MAX_ATTEMPS and (ret is None or len(ret.all) <= 0):
            attemps += 1
            current_decent_win_rate = (
                decent_win_rate if current_decent_win_rate is None else (current_decent_win_rate - 1)
            )
            current_decent_win_rate = (
                round(current_decent_win_rate, ndigits=2) if current_decent_win_rate is not None else None
            )
            ret = self._get_backtesting_ranking(
                disable_minimal_trades=disable_minimal_trades,
                disable_decent_win_rate=disable_decent_win_rate,
                decent_win_rate=current_decent_win_rate
                if current_decent_win_rate is not None and current_decent_win_rate > 0
                else None,
                min_profit_factor=None,
                min_sqn=None,
                executions_results=executions_results,
            )
        # Disable decent win rate
        if ret is None:
            ret = self._get_backtesting_ranking(
                disable_minimal_trades=disable_minimal_trades,
                disable_decent_win_rate=True,
                decent_win_rate=0.0,
                min_profit_factor=None,
                min_sqn=None,
                executions_results=executions_results,
            )
        if ret is None:
            ret = self._get_backtesting_ranking(
                disable_minimal_trades=True,
                disable_decent_win_rate=True,
                decent_win_rate=0.0,
                min_profit_factor=None,
                min_sqn=None,
                executions_results=executions_results,
            )
        return ret

    def _get_backtesting_ranking(
        self,
        *,
        disable_minimal_trades: bool,
        disable_decent_win_rate: bool,
        decent_win_rate: float,
        min_profit_factor: float | None,
        min_sqn: float | None,
        executions_results: list[BacktestingExecutionResult],
    ) -> BacktestingInOutOfSampleRanking:
        # 4. Filter for viable strategies to analyze
        # We only care about strategies that were profitable and had a meaningful number of trades

        # 4.1. Calculate the minimum number of trades required to consider a strategy for stats
        num_of_weeks_downloaded = DEFAULT_MONTHS_BACK * 4
        min_trades_for_stats = max(
            MIN_TRADES_FOR_DEFAULT_MONTHS_BACK, math.ceil(num_of_weeks_downloaded * MIN_ENTRIES_PER_WEEK)
        )
        profitable_results = [
            res
            for res in executions_results
            if res.outcomes.net_profit_amount > 0
            and (disable_minimal_trades or res.outcomes.number_of_trades >= min_trades_for_stats)
            and (disable_decent_win_rate or res.outcomes.win_rate >= decent_win_rate)
            and (min_sqn is None or res.outcomes.sqn >= min_sqn)
            and (min_profit_factor is None or res.outcomes.profit_factor >= min_profit_factor)
        ]
        best_overall, highest_quality, best_profitable, best_win_rate = None, None, None, None
        if profitable_results:
            # --- Category 1: Best Overall (Profit x Win Rate x Trades) ---
            best_overall = max(
                profitable_results,
                key=lambda r: r.outcomes.net_profit_percentage * r.outcomes.win_rate * r.outcomes.number_of_trades,
            )
            # --- Category 2: Highest Quality (Return x Win Rate) ---
            highest_quality = max(
                profitable_results, key=lambda r: r.outcomes.net_profit_percentage * r.outcomes.win_rate
            )
            # --- Category 3: Best Profitable Configuration ---
            best_profitable = max(profitable_results, key=lambda r: r.outcomes.net_profit_amount)
            # --- Category 4: Best Win Rate ---
            # First, find the maximum win rate that was achieved
            max_win_rate = max(p.outcomes.win_rate for p in profitable_results)
            # Create a group of "elite" candidates with a win rate close to the maximum
            # (e.g., all strategies within 5 percentage points of the best result)
            elite_win_rate_candidates = [
                res for res in profitable_results if res.outcomes.win_rate >= (max_win_rate - 5.0)
            ]
            # From that elite group, pick the one with the highest NET RETURN.
            if elite_win_rate_candidates:
                best_win_rate = max(elite_win_rate_candidates, key=lambda r: r.outcomes.net_profit_amount)
            else:  # Fallback in case the list is empty (should not happen)
                best_win_rate = max(profitable_results, key=lambda r: r.outcomes.win_rate)

        ret = BacktestingInOutOfSampleRanking(
            best_overall=BacktestingInOutOfSampleExecutionResult.from_(best_overall) if best_overall else None,
            highest_quality=BacktestingInOutOfSampleExecutionResult.from_(highest_quality) if highest_quality else None,
            best_profitable=BacktestingInOutOfSampleExecutionResult.from_(best_profitable) if best_profitable else None,
            best_win_rate=BacktestingInOutOfSampleExecutionResult.from_(best_win_rate) if best_win_rate else None,
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
        sp_tp_tuples: list[tuple[bool, float, float]] | None = None,
        tp_filter: TakeProfitFilter = "all",
        apply_heuristics: bool = True,
        echo_fn: Callable[[str], None] | None = None,
    ) -> list[BuySellSignalsConfigItem]:
        enable_exit_on_divergence_signal_values: list[bool] = [True, False]
        # Group SL/TP pairs by SL value to ensure we have unique SL values when TP is disabled
        sp_tp_tuples = sp_tp_tuples or self._get_sp_tp_tuples(tp_filter=tp_filter)

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
            product(
                ema_short_mid_pairs_as_tuples,
                sp_tp_tuples,
                adx_threshold_values,
                vol_buy_cases,
                vol_sell_cases,
                enable_exit_on_divergence_signal_values,
            )
        )
        if echo_fn:
            echo_fn(f"FULL RAW COMBINATIONS TO TEST: {len(full_cartesian_product)}")
        # --- HEURISTIC PRUNING ---
        ret: list[BuySellSignalsConfigItem] = self._convert_cartesian_product_to_config_items(
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
                enable_exit_on_divergence_signal,
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
                enable_exit_on_sell_signal=True,
                enable_exit_on_divergence_signal=enable_exit_on_divergence_signal,
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
        # Rule 5: For fast EMAs (which can be noisy), enforce a confirmation filter (either ADX or Volume).
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
            outcomes=BacktestingOutcomes(
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
            ),
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

    def _convert_timeframe_to_interval(self, timeframe: str) -> int:
        # The interval of entries in minutes: 1, 5, 15, 30, 60 (1 hour), 240 (4 hours), 1440 (1 day)
        td = pd.Timedelta(timeframe)
        ret = int(td.total_seconds() // 60)
        return ret

    def _convert_timeframe_to_days(self, timeframe: str) -> float:
        td = pd.Timedelta(timeframe)
        ret = td.total_seconds() / 86400  # 86400 seconds in a day
        return ret
