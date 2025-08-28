import typer

from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.scripts.vo import BacktestingExecutionResult


# --- Helper function to print results in a clean format ---
def echo_backtesting_execution_result(result: BacktestingExecutionResult) -> None:
    item: BuySellSignalsConfigItem = result.parameters
    typer.secho("⚙️  Parameters:", fg=typer.colors.BLUE)
    typer.echo(
        f"📈 EMA Short Value = {item.ema_short_value}\n"
        + f"📉 EMA Mid Value = {item.ema_mid_value}\n"
        + f"📐 EMA Long Value = {item.ema_long_value}\n"
        + f"🛡️ Stop Loss ATR Factor = {item.stop_loss_atr_multiplier}\n"
        + f"🏁 Take Profit ATR Factor = {item.take_profit_atr_multiplier}\n"
        + f"📶 Filter Noise using ADX? = {'🟢' if item.filter_noise_using_adx else '🟥'}\n"
        + f"🔦 ADX Threshold = {item.adx_threshold if item.filter_noise_using_adx else '(not applicable)'}\n"  # noqa: E501
        + f"🚩 Apply Relative Volume Filter? = {'🟢' if item.apply_volume_filter else '🟥'}\n"
        + f"💣 Volume Conviction on SELL 1H enabled? = {'🟢' if item.enable_volume_conviction_on_sell else '🟥'}\n"
        + f"🔊 Min. Rel. Volume Threshold = {item.min_volume_threshold if item.apply_volume_filter else '(not applicable)'}\n"  # noqa: E501
        + f"🔇 Max. Rel. Volume Threshold = {item.max_volume_threshold if item.apply_volume_filter else '(not applicable)'}\n"  # noqa: E501
        + f"🚨 Auto-Exit SELL 1h enabled? = {'🟢' if item.auto_exit_sell_1h else '🟥'}\n"
        + f"🎯 Auto-Exit Take Profit enabled? = {'🟢' if item.auto_exit_atr_take_profit else '🟥'}"
    )
    typer.secho("\n--- 📝 Summary ---", fg=typer.colors.MAGENTA, bold=True)
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
    typer.echo(f"Number of Trades [n]:        {number_of_trades}")
    typer.echo(f"Win Rate [%]:                {win_rate_str}")
    typer.echo(f"Net Profit/Loss [EUR]:       {return_eur_str}")
    typer.echo(f"Net Return [%]:              {return_pct_str}")
