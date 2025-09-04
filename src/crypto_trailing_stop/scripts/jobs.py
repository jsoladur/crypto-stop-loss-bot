import pandas as pd

from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.scripts.vo import BacktestingExecutionResult


def run_single_backtest_combination(
    simulated_bs_config: BuySellSignalsConfigItem, initial_cash: float, df: pd.DataFrame, timeframe: str = "1h"
) -> BacktestingExecutionResult | None:
    """
    Runs a single backtest for one combination of parameters. Designed to be called in parallel.
    """
    import logging
    import warnings

    from crypto_trailing_stop.scripts.services import BacktestingCliService

    warnings.filterwarnings("ignore")
    logger = logging.getLogger(__name__)

    backtesting_cli_service = BacktestingCliService()
    ret: BacktestingExecutionResult | None = None
    try:
        # We use df.copy() to ensure each process gets its own data
        ret, *_ = backtesting_cli_service.execute_backtesting(
            simulated_bs_config=simulated_bs_config,
            initial_cash=initial_cash,
            df=df.copy(),
            timeframe=timeframe,
            use_tqdm=False,
        )
    except Exception as e:
        # We use echo_fn for thread-safe printing if needed
        logger.warning(f"Backtest failed for params {simulated_bs_config}: {e}", exc_info=True)
    return ret
