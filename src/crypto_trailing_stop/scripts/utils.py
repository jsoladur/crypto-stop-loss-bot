import typer

from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.scripts.vo import BacktestingExecutionResult


# --- Helper function to print results in a clean format ---
def echo_backtesting_execution_result(result: BacktestingExecutionResult) -> None:
    simulated_bs_config: BuySellSignalsConfigItem = result.parameters
    typer.secho("⚙️  Parameters:", fg=typer.colors.BLUE)
    typer.echo(f"  - Stop Loss Multiplier: {simulated_bs_config.stop_loss_atr_multiplier}x ATR")
    typer.echo(
        f"  - Take Profit Multiplier: {simulated_bs_config.take_profit_atr_multiplier if simulated_bs_config.auto_exit_atr_take_profit else 'N/A'}x ATR"  # noqa: E501
    )  # noqa: E501
    typer.echo(
        f"  - ADX Filter: {'Enabled' if simulated_bs_config.filter_noise_using_adx and simulated_bs_config.adx_threshold > 0 else 'Disabled'}, Threshold: {simulated_bs_config.adx_threshold if simulated_bs_config.filter_noise_using_adx and simulated_bs_config.adx_threshold > 0 else 'N/A'}"  # noqa: E501
    )
    typer.echo(
        f"  - Volume Filter: {'Enabled' if simulated_bs_config.apply_volume_filter and simulated_bs_config.volume_threshold > 0 else 'Disabled'}, Threshold: {simulated_bs_config.volume_threshold if simulated_bs_config.apply_volume_filter and simulated_bs_config.volume_threshold > 0 else 'N/A'}"  # noqa: E501
    )
    typer.echo(
        f"  - Take Profit: {'Enabled' if simulated_bs_config.auto_exit_atr_take_profit else 'Disabled'}"  # noqa: E501
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
