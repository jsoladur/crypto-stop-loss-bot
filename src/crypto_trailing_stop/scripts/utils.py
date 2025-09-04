import typer

from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.scripts.vo import BacktestingExecutionResult


# --- Helper function to print results in a clean format ---
def echo_backtesting_execution_result(result: BacktestingExecutionResult) -> None:
    number_of_trades = typer.style(
        str(result.number_of_trades), fg=typer.colors.GREEN if result.number_of_trades > 0 else typer.colors.RED
    )
    # Style the output strings
    win_rate_str = typer.style(
        f"{result.win_rate:.2f}%", fg=typer.colors.GREEN if result.win_rate > 50 else typer.colors.RED
    )
    return_eur_str = typer.style(
        f"{result.net_profit_amount:.2f} EUR",
        fg=typer.colors.GREEN if result.net_profit_amount > 0 else typer.colors.RED,
    )
    return_pct_str = typer.style(
        f"{(result.net_profit_percentage):.2f}%",
        fg=typer.colors.GREEN if result.net_profit_percentage > 0 else typer.colors.RED,
    )
    return_profit_factor = typer.style(
        f"{(result.profit_factor):.2f}", fg=typer.colors.GREEN if result.profit_factor > 1.5 else typer.colors.RED
    )
    return_buy_and_hold_return_str = typer.style(
        f"{(result.buy_and_hold_return_percentage):.2f}%",
        fg=typer.colors.GREEN if result.buy_and_hold_return_percentage > 0 else typer.colors.RED,
    )
    return_best_trade_str = typer.style(
        f"{(result.best_trade_percentage):.2f}%",
        fg=typer.colors.GREEN if result.best_trade_percentage > 0 else typer.colors.RED,
    )
    return_worst_trade_str = typer.style(
        f"{(result.worst_trade_percentage):.2f}%",
        fg=typer.colors.GREEN if result.worst_trade_percentage > 0 else typer.colors.RED,
    )
    return_sqn_str = typer.style(f"{(result.sqn):.2f}", fg=typer.colors.GREEN if result.sqn > 2.0 else typer.colors.RED)

    item: BuySellSignalsConfigItem = result.parameters

    typer.secho("⚙️  Parameters:", fg=typer.colors.BLUE)
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
        f"🎯 Exit on Take Profit enabled? = {'🟢' if item.enable_exit_on_take_profit else '🟥'}"
    )
    typer.secho("--- 📝 Summary ---", fg=typer.colors.MAGENTA, bold=True)
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
        f"Avg. Drawdown [%]:           {typer.style(str(result.avg_drawdown_percentage) + '%', fg=typer.colors.RED)}"
    )
    typer.echo(
        f"Max. Drawdown [%]:           {typer.style(str(result.max_drawdown_percentage) + '%', fg=typer.colors.RED)}"
    )
    typer.echo(
        f"Avg. Trade Dur. [days]:      {typer.style(str(result.avg_trade_duration_in_days), fg=typer.colors.GREEN)}"
    )
    typer.echo(
        f"Max. Trade Dur. [days]:      {typer.style(str(result.max_trade_duration_in_days), fg=typer.colors.GREEN)}"
    )
    typer.echo(
        f"Avg. Drawdown Dur. [days]:   {typer.style(str(result.avg_drawdown_duration_in_days), fg=typer.colors.RED)}"
    )
    typer.echo(
        f"Max. Drawdown Dur. [days]:   {typer.style(str(result.max_drawdown_duration_in_days), fg=typer.colors.RED)}"
    )
    typer.echo(f"SQN [System Quality Number]: {return_sqn_str}")
