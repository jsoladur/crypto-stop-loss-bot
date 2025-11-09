import pandas as pd
import typer

from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.scripts.vo import (
    BacktestingExecutionResult,
    BacktestingInOutOfSampleExecutionResult,
    BacktestingOutcomes,
)


def _echo_parameters(item: BuySellSignalsConfigItem) -> None:
    typer.echo(
        f"📈 EMA Short = {item.ema_short_value}\n"
        f"📉 EMA Mid = {item.ema_mid_value}\n"
        f"📐 EMA Long = {item.ema_long_value}\n"
        f"🛡️ SL ATR x = {item.stop_loss_atr_multiplier}\n"
        f"🏁 TP ATR x = {item.take_profit_atr_multiplier}\n"
        f"📶 ADX Filter enabled? = {'🟢' if item.enable_adx_filter else '🟥'}\n"
        f"🔦 ADX Threshold = {item.adx_threshold if item.enable_adx_filter else '(n/a)'}\n"
        f"🚩 BUY Volume Filter enabled? = {'🟢' if item.enable_buy_volume_filter else '🟥'}\n"
        f"🔊 BUY Min Volume Threshold = {item.buy_min_volume_threshold if item.enable_buy_volume_filter else '(n/a)'}\n"
        f"🔇 BUY Max Volume Threshold = {item.buy_max_volume_threshold if item.enable_buy_volume_filter else '(n/a)'}\n"
        f"💣 SELL Volume Filter enabled? = {'🟢' if item.enable_sell_volume_filter else '🟥'}\n"
        f"🔊 SELL Min Volume Threshold = {item.sell_min_volume_threshold if item.enable_sell_volume_filter else '(n/a)'}\n"  # noqa: E501
        f"🚨 Exit on SELL Signal enabled? = {'🟢' if item.enable_exit_on_sell_signal else '🟥'}\n"
        f"💀 Exit on BEARISH Divergence enabled? = {'🟢' if item.enable_exit_on_divergence_signal else '🟥'}\n"
        f"🎯 Exit on Take Profit enabled? = {'🟢' if item.enable_exit_on_take_profit else '🟥'}"
    )


def _echo_outcomes(outcomes: BacktestingOutcomes) -> None:
    number_of_trades = typer.style(
        str(outcomes.number_of_trades), fg=typer.colors.GREEN if outcomes.number_of_trades > 0 else typer.colors.RED
    )
    # Style the output strings
    win_rate_str = typer.style(
        f"{outcomes.win_rate:.2f}%", fg=typer.colors.GREEN if outcomes.win_rate > 50 else typer.colors.RED
    )
    return_eur_str = typer.style(
        f"{outcomes.net_profit_amount:.2f} EUR",
        fg=typer.colors.GREEN if outcomes.net_profit_amount > 0 else typer.colors.RED,
    )
    return_pct_str = typer.style(
        f"{(outcomes.net_profit_percentage):.2f}%",
        fg=typer.colors.GREEN if outcomes.net_profit_percentage > 0 else typer.colors.RED,
    )
    return_profit_factor = typer.style(
        f"{(outcomes.profit_factor):.2f}", fg=typer.colors.GREEN if outcomes.profit_factor > 1.5 else typer.colors.RED
    )
    return_buy_and_hold_return_str = typer.style(
        f"{(outcomes.buy_and_hold_return_percentage):.2f}%",
        fg=typer.colors.GREEN if outcomes.buy_and_hold_return_percentage > 0 else typer.colors.RED,
    )
    return_best_trade_str = typer.style(
        f"{(outcomes.best_trade_percentage):.2f}%",
        fg=typer.colors.GREEN if outcomes.best_trade_percentage > 0 else typer.colors.RED,
    )
    return_worst_trade_str = typer.style(
        f"{(outcomes.worst_trade_percentage):.2f}%",
        fg=typer.colors.GREEN if outcomes.worst_trade_percentage > 0 else typer.colors.RED,
    )
    return_sqn_str = typer.style(
        f"{(outcomes.sqn):.2f}", fg=typer.colors.GREEN if outcomes.sqn > 2.0 else typer.colors.RED
    )
    typer.echo(f"Number of Trades [n]:        {number_of_trades}")
    typer.echo(f"Win Rate [%]:                {win_rate_str}")
    typer.echo(f"Net Profit/Loss [EUR]:       {return_eur_str}")
    typer.echo(f"Net Return [%]:              {return_pct_str}")
    typer.secho("--- 🗂️ Metadata ---", fg=typer.colors.MAGENTA, bold=True)
    typer.echo(f"Buy & Hold Return [%]:       {return_buy_and_hold_return_str}")
    typer.echo(f"Profit Factor[n]:            {return_profit_factor}")
    typer.echo(f"Best Trade [%]:              {return_best_trade_str}")
    typer.echo(f"Worst Trade [%]:             {return_worst_trade_str}")
    typer.echo(
        f"Avg. Drawdown [%]:           {typer.style(str(outcomes.avg_drawdown_percentage) + '%', fg=typer.colors.RED)}"
    )
    typer.echo(
        f"Max. Drawdown [%]:           {typer.style(str(outcomes.max_drawdown_percentage) + '%', fg=typer.colors.RED)}"
    )
    typer.echo(
        f"Avg. Trade Dur. [days]:      {typer.style(str(outcomes.avg_trade_duration_in_days), fg=typer.colors.GREEN)}"
    )
    typer.echo(
        f"Max. Trade Dur. [days]:      {typer.style(str(outcomes.max_trade_duration_in_days), fg=typer.colors.GREEN)}"
    )
    typer.echo(
        f"Avg. Drawdown Dur. [days]:   {typer.style(str(outcomes.avg_drawdown_duration_in_days), fg=typer.colors.RED)}"
    )
    typer.echo(
        f"Max. Drawdown Dur. [days]:   {typer.style(str(outcomes.max_drawdown_duration_in_days), fg=typer.colors.RED)}"
    )
    typer.echo(f"SQN [System Quality Number]: {return_sqn_str}")


def get_default_candles_filename(symbol: str) -> str:
    return f"{symbol.replace('/', '_')}.csv"


def get_full_relative_path_by_filename(filename: str) -> str:
    return f"data/candles/{filename}"


def load_candlestick_dataframe_from_file(filename: str) -> pd.DataFrame:
    data_file = get_full_relative_path_by_filename(filename)
    df = pd.read_csv(data_file)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def echo_backtesting_execution_result(result: BacktestingExecutionResult) -> None:
    typer.secho("⚙️  Parameters:", fg=typer.colors.BLUE)
    _echo_parameters(result.parameters)
    typer.secho("--- 📝 Outcomes ---", fg=typer.colors.MAGENTA, bold=True)
    _echo_outcomes(result.outcomes)


def echo_backtesting_in_out_of_sample_result(result: BacktestingInOutOfSampleExecutionResult) -> None:
    typer.secho("⚙️  Parameters:", fg=typer.colors.BLUE)
    _echo_parameters(result.parameters)
    typer.secho("--- 📝 IN-SAMPLE Outcomes ---", fg=typer.colors.MAGENTA, bold=True)
    _echo_outcomes(result.in_sample_outcomes)
    typer.secho("--- 📝 OUT-OF-SAMPLE Outcomes ---", fg=typer.colors.MAGENTA, bold=True)
    _echo_outcomes(result.out_of_sample_outcomes)
