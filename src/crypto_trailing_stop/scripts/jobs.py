import pandas as pd

from crypto_trailing_stop.scripts.vo import BacktestingExecutionResult


def run_single_backtest_combination(
    params: tuple[tuple[int, ...], ...], symbol: str, initial_cash: float, df: pd.DataFrame
) -> BacktestingExecutionResult | None:
    """
    Runs a single backtest for one combination of parameters. Designed to be called in parallel.
    """
    import logging
    import warnings

    from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
    from crypto_trailing_stop.scripts.services import BacktestingCliService

    warnings.filterwarnings("ignore")
    logger = logging.getLogger(__name__)

    backtesting_cli_service = BacktestingCliService()

    (
        (ema_short, ema_mid),
        (enable_exit_on_take_profit, sl_multiplier, tp_multiplier),
        adx_threshold,
        (enable_buy_volume_filter, buy_min_volume_threshold, buy_max_volume_threshold),
        (enable_sell_volume_filter, sell_min_volume_threshold),
        *_,
    ) = params
    ret: BacktestingExecutionResult | None = None
    try:
        simulated_bs_config = BuySellSignalsConfigItem(
            symbol=symbol,
            ema_short_value=ema_short,
            ema_mid_value=ema_mid,
            ema_long_value=200,
            stop_loss_atr_multiplier=sl_multiplier,
            take_profit_atr_multiplier=tp_multiplier,
            enable_adx_filter=adx_threshold > 0,  # ADX is enabled if threshold > 0
            adx_threshold=adx_threshold,
            enable_buy_volume_filter=enable_buy_volume_filter,
            buy_min_volume_threshold=buy_min_volume_threshold,
            buy_max_volume_threshold=buy_max_volume_threshold,
            enable_sell_volume_filter=enable_sell_volume_filter,
            sell_min_volume_threshold=sell_min_volume_threshold,
            enable_exit_on_take_profit=enable_exit_on_take_profit,
        )
        # We use df.copy() to ensure each process gets its own data
        ret, *_ = backtesting_cli_service.execute_backtesting(
            simulated_bs_config=simulated_bs_config, initial_cash=initial_cash, df=df.copy(), use_tqdm=False
        )
    except Exception as e:
        # We use echo_fn for thread-safe printing if needed
        logger.warning(f"Backtest failed for params {params}: {e}")
    return ret
