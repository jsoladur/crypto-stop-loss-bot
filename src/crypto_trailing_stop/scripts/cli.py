import dataclasses
import os
import warnings
from pathlib import Path
from typing import get_args

import click
import pandas as pd
import pydash
import typer
from faker import Faker

from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.scripts.constants import DECENT_WIN_RATE_THRESHOLD, DEFAULT_MONTHS_BACK
from crypto_trailing_stop.scripts.services import BacktestingCliService
from crypto_trailing_stop.scripts.utils import echo_backtesting_execution_result
from crypto_trailing_stop.scripts.vo import TakeProfitFilter

warnings.filterwarnings("ignore")

# ------------------------------------------------------------------------------------
# Mock env variables
# ------------------------------------------------------------------------------------

# .env.backtest
faker = Faker()
os.environ["TELEGRAM_BOT_TOKEN"] = f"{faker.pyint()}:{faker.uuid4().replace('-', '_')}"
os.environ["BIT2ME_API_BASE_URL"] = "https://api.example.com"  # nosec: B105
os.environ["BIT2ME_API_KEY"] = "placeholder"  # nosec: B105
os.environ["BIT2ME_API_SECRET"] = "placeholder"  # nosec: B105
os.environ["AUTHORIZED_GOOGLE_USER_EMAILS_COMMA_SEPARATED"] = "user@example.com"
os.environ["GOOGLE_OAUTH_CLIENT_ID"] = "placeholder"
os.environ["GOOGLE_OAUTH_CLIENT_SECRET"] = "placeholder"  # nosec: B105

# ------------------------------------------------------------------------------------
# --- Typer CLI Application ---
# ------------------------------------------------------------------------------------

app = typer.Typer()

backtesting_cli_service = BacktestingCliService()


@app.command()
def download_data(
    symbol: str = typer.Argument(..., help="The symbol to download, e.g., ETH/EUR"),
    exchange: str = typer.Option("binance", help="The name of the exchange to use."),
    timeframe: str = typer.Option("1h", help="The timeframe to download data for."),
    months_back: int = typer.Option(DEFAULT_MONTHS_BACK, help="The number of months of data to download."),
):
    """
    Downloads the last 1 year of 1H historical data for a symbol and saves it to data/candles.
    """
    symbol = symbol.strip().upper()
    try:
        typer.secho(f"📥 Starting download for {symbol} on 1h timeframe...", fg=typer.colors.BLUE)
        all_ohlcv = backtesting_cli_service.download_backtesting_data(
            symbol, exchange, timeframe, months_back, echo_fn=typer.secho
        )
        typer.secho(f"✅ Download complete. {len(all_ohlcv)} candles fetched.", fg=typer.colors.GREEN)
        if all_ohlcv:
            df = pd.DataFrame(all_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            os.makedirs("data/candles", exist_ok=True)
            filename = f"data/candles/{symbol.replace('/', '_')}.csv"
            df.to_csv(filename, index=False)
            typer.echo(f"💾 Data saved to '{filename}'")
    except Exception as e:
        typer.secho(f"❌ Error downloading data: {e}", fg=typer.colors.RED)


@app.command()
def backtesting(
    symbol: str = typer.Argument(..., help="The symbol to backtest, e.g., ETH/EUR"),
    timeframe: str = typer.Option("1h", help="The timeframe to download data for."),
    # EMA/ADX parameters
    ema_short: int = typer.Option(9, help="Length of the short EMA."),
    ema_mid: int = typer.Option(21, help="Length of the medium EMA."),
    ema_long: int = typer.Option(200, help="Length of the long EMA."),
    filter_adx: bool = typer.Option(True, help="Enable/disable the ADX noise filter."),
    adx_threshold: int = typer.Option(20, help="ADX threshold for trend confirmation."),
    enable_buy_volume_filter: bool = typer.Option(True, help="Enable/disable BUY volume filter."),
    buy_min_volume_threshold: float = typer.Option(0.5, help="Enable/disable the buy minimum volume filter."),
    buy_max_volume_threshold: float = typer.Option(3.5, help="Enable/disable the buy maximum volume filter."),
    enable_sell_volume_filter: bool = typer.Option(False, help="Enable/disable SELL volume filter."),
    sell_min_volume_threshold: float = typer.Option(1.0, help="Enable/disable the sell minimum volume filter."),
    enable_tp: bool = typer.Option(False, "--enable-tp", help="Enable the ATR-based Take Profit."),
    sl_multiplier: float = typer.Option(2.5, help="ATR multiplier for Stop Loss."),
    tp_multiplier: float = typer.Option(3.5, help="ATR multiplier for Take Profit."),
    # Initial cash and debug parameters
    initial_cash: float = typer.Option(3_000, help="Intial cash for the backtest."),
    show_plot: bool = typer.Option(False, help="Show the backtesting plot."),
    debug: bool = typer.Option(False, help="Enable debug, opening backtesting plot."),
):
    """
    Runs a backtest of the signal strategy for a symbol, using local data and configurable parameters.
    """
    symbol = symbol.strip().upper()
    # Create the config object from the CLI options
    try:
        data_file = f"data/candles/{symbol.replace('/', '_')}.csv"
        df = pd.read_csv(data_file)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.dropna(inplace=True)
        df.reset_index(drop=True, inplace=True)

        typer.echo(f"📊 {len(df)} candles loaded. Calculating indicators and signals...")

        simulated_bs_config = BuySellSignalsConfigItem(
            symbol=symbol,
            ema_short_value=ema_short,
            ema_mid_value=ema_mid,
            ema_long_value=ema_long,
            stop_loss_atr_multiplier=sl_multiplier,
            take_profit_atr_multiplier=tp_multiplier,
            enable_adx_filter=filter_adx,
            adx_threshold=adx_threshold,
            enable_buy_volume_filter=enable_buy_volume_filter,
            buy_min_volume_threshold=buy_min_volume_threshold,
            buy_max_volume_threshold=buy_max_volume_threshold,
            enable_sell_volume_filter=enable_sell_volume_filter,
            sell_min_volume_threshold=sell_min_volume_threshold,
            enable_exit_on_sell_signal=True,
            enable_exit_on_take_profit=enable_tp,
        )
        current_execution_result, bt, stats = backtesting_cli_service.execute_backtesting(
            simulated_bs_config=simulated_bs_config,
            initial_cash=initial_cash,
            df=df,
            timeframe=timeframe,
            echo_fn=typer.secho,
        )

        if debug:
            os.makedirs("data/indicators", exist_ok=True)
            filename = f"data/indicators/{symbol.replace('/', '_')}_indicators.csv"
            df.to_csv(filename, index=False)
            typer.echo(f"💾 Indicators outcomes saved to '{filename}'")
            typer.echo("-----")
            typer.echo(stats)
            typer.echo("-----")

        typer.secho(f"\n--- 📈 {symbol.upper()} BACKTEST RESULTS ---", fg=typer.colors.MAGENTA, bold=True)
        echo_backtesting_execution_result(current_execution_result)
        if show_plot:
            bt.plot()
    except FileNotFoundError:
        typer.secho(f"❌ Error: Data file '{data_file}' not found.", fg=typer.colors.RED)
        typer.echo(f"👉 Please run 'cli download-data {symbol}' first.")
        raise typer.Exit()


@app.command()
def research(
    symbol: str = typer.Argument(..., help="The symbol to backtest, e.g., ETH/EUR"),
    initial_cash: float = typer.Option(3_000, help="Intial cash for the backtest."),
    exchange: str = typer.Option("binance", help="The name of the exchange to use."),
    timeframe: str = typer.Option("1h", help="The timeframe to download data for."),
    months_back: int = typer.Option(DEFAULT_MONTHS_BACK, help="The number of months of data to download."),
    disable_minimal_trades: bool = typer.Option(False, help="Disable the minimal trades threshold."),
    disable_decent_win_rate: bool = typer.Option(False, help="Disable the decent win rate threshold."),
    decent_win_rate: float = typer.Option(
        DECENT_WIN_RATE_THRESHOLD, help="The minimum win rate to consider a configuration decent."
    ),
    min_profit_factor: float = typer.Option(None, help="Minimal profit factor to consider a valid the strategy"),
    min_sqn: float = typer.Option(None, help="Minimal SQN to consider a valid the strategy"),
    tp_filter: str = typer.Option(
        "all",
        "--tp-filter",
        help="Filter backtesting by Take Profit: 'all' (default), 'enabled', or 'disabled'.",
        case_sensitive=False,
        click_type=click.Choice(list(get_args(TakeProfitFilter)), case_sensitive=False),
    ),
    from_parquet: Path = typer.Option(
        None, "--from-parquet", help="Path to a Parquet file with precomputed backtesting results (skips execution)."
    ),
    download_candles: bool = typer.Option(True, help="Download data before running the research."),
    disable_progress_bar: bool = typer.Option(False, help="Disable the progress bar."),
):
    """
    Runs a research process to find the best parameters for a symbol, using local data.
    """
    symbol = symbol.strip().upper()
    try:
        df: pd.DataFrame | None = None
        if from_parquet is None:
            if download_candles:
                download_data(symbol=symbol, exchange=exchange, timeframe=timeframe, months_back=months_back)
            data_file = f"data/candles/{symbol.replace('/', '_')}.csv"
            df = pd.read_csv(data_file)
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            df.dropna(inplace=True)
            df.reset_index(drop=True, inplace=True)
        execution_summary = backtesting_cli_service.find_out_best_parameters(
            symbol=symbol,
            timeframe=timeframe,
            initial_cash=initial_cash,
            downloaded_months_back=months_back,
            disable_minimal_trades=disable_minimal_trades,
            disable_decent_win_rate=disable_decent_win_rate,
            decent_win_rate=decent_win_rate,
            min_profit_factor=min_profit_factor,
            min_sqn=min_sqn,
            tp_filter=tp_filter,
            df=df,
            from_parquet=from_parquet,
            disable_progress_bar=disable_progress_bar,
            echo_fn=typer.secho,
        )
        # Print the summary
        typer.secho(f"\n--- 🔬 {symbol.upper()} RESEARCH RESULTS ---", fg=typer.colors.MAGENTA, bold=True)
        execution_summary_fields = dataclasses.fields(execution_summary)
        if all(getattr(execution_summary, field.name) is None for field in execution_summary_fields):
            typer.secho("❌ No decent configuration found. Try lowering the win rate threshold.", fg=typer.colors.RED)
            raise typer.Exit()
        else:
            typer.secho("✅ Decent configurations found:", fg=typer.colors.GREEN)
            for field in execution_summary_fields:
                value = getattr(execution_summary, field.name)
                if value:
                    typer.secho(f"\n--- {symbol.upper()} 🏆 Champion: {pydash.start_case(field.name)} ---")
                    echo_backtesting_execution_result(value)

    except FileNotFoundError:
        typer.secho(f"❌ Error: Data file '{data_file}' not found.", fg=typer.colors.RED)
        typer.echo(f"👉 Please run 'cli download-data {symbol}' first.")
        raise typer.Exit()


if __name__ == "__main__":
    app()
