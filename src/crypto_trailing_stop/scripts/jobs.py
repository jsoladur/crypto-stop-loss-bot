import pandas as pd

from crypto_trailing_stop.scripts.vo import BacktestingExecutionResult


def run_single_backtest_combination(
    params: tuple[str, ...], symbol: str, initial_cash: float, df: pd.DataFrame
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

    ema_short_and_ema_mid, sp_percent_and_tp_factors, adx_threshold, volume_threshold = params
    ema_short, ema_mid = map(int, ema_short_and_ema_mid.split("/"))
    sl_multiplier, tp_multiplier = map(float, sp_percent_and_tp_factors.split("/"))
    ret: BacktestingExecutionResult | None = None
    try:
        simulated_bs_config = BuySellSignalsConfigItem(
            symbol=symbol,
            ema_short_value=ema_short,
            ema_mid_value=ema_mid,
            ema_long_value=200,
            stop_loss_atr_multiplier=sl_multiplier,
            take_profit_atr_multiplier=tp_multiplier,
            filter_noise_using_adx=adx_threshold > 0,  # ADX is enabled if threshold > 0
            adx_threshold=adx_threshold,
            apply_volume_filter=volume_threshold > 0,  # Volume filter is enabled if threshold > 0
            volume_threshold=volume_threshold,
        )
        # We use df.copy() to ensure each process gets its own data
        ret, *_ = backtesting_cli_service.execute_backtesting(
            simulated_bs_config=simulated_bs_config, initial_cash=initial_cash, df=df.copy(), use_tqdm=False
        )
    except Exception as e:
        # We use echo_fn for thread-safe printing if needed
        logger.warning(f"Backtest failed for params {params}: {e}")
    return ret
