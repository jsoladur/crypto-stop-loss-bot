import dataclasses
import logging
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
from crypto_trailing_stop.scripts.constants import (
    DECENT_WIN_RATE_THRESHOLD,
    DEFAULT_MONTHS_BACK,
    OUT_OF_SAMPLE_MONTHS_BACK,
)
from crypto_trailing_stop.scripts.services import BacktestingCliService
from crypto_trailing_stop.scripts.utils import (
    echo_backtesting_execution_result,
    echo_backtesting_in_out_of_sample_result,
    get_default_candles_filename,
    get_full_relative_path_by_filename,
    load_candlestick_dataframe_from_file,
)
from crypto_trailing_stop.scripts.vo import TakeProfitFilter

logger = logging.getLogger(__name__)

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
    exchange: str = typer.Option("mexc", help="The name of the exchange to use."),
    timeframe: str = typer.Option("1h", help="The timeframe to download data for."),
    months_back: int = typer.Option(DEFAULT_MONTHS_BACK, help="The number of months of data to download."),
    months_offset: int = typer.Option(0, help="Allow to download data with a offset of months."),
    filename: str = typer.Option(None, help="The name of the file to save the data to."),
):
    """
    Downloads the last 1 year of 1H historical data for a symbol and saves it to data/candles.
    """
    symbol = symbol.strip().upper()
    filename = filename or get_default_candles_filename(symbol)
    try:
        typer.secho(f"📥 Starting download for {exchange.upper()} :: {symbol} on 1h timeframe...", fg=typer.colors.BLUE)
        all_ohlcv = backtesting_cli_service.download_backtesting_data(
            symbol, exchange, timeframe, months_back, months_offset, echo_fn=typer.secho
        )
        typer.secho(f"✅ Download complete. {len(all_ohlcv)} candles fetched.", fg=typer.colors.GREEN)
        if all_ohlcv:
            df = pd.DataFrame(all_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            os.makedirs("data/candles", exist_ok=True)
            file_path = f"data/candles/{filename}"
            df.to_csv(file_path, index=False)
            typer.echo(f"💾 Data saved to '{file_path}'")
    except Exception as e:
        typer.secho(f"❌ Error downloading data: {e}", fg=typer.colors.RED)


@app.command()
def backtesting(
    symbol: str = typer.Argument(..., help="The symbol to backtest, e.g., ETH/EUR"),
    exchange: str = typer.Option("mexc", help="The name of the exchange to use."),
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
    sell_on_divergence: bool = typer.Option(True, help="Enable/disable the sell on Bearish divergence filter."),
    enable_tp: bool = typer.Option(False, "--enable-tp", help="Enable the ATR-based Take Profit."),
    sl_multiplier: float = typer.Option(2.5, help="ATR multiplier for Stop Loss."),
    tp_multiplier: float = typer.Option(3.5, help="ATR multiplier for Take Profit."),
    # Initial cash and debug parameters
    initial_cash: float = typer.Option(3_000, help="Intial cash for the backtest."),
    show_plot: bool = typer.Option(False, help="Show the backtesting plot."),
    debug: bool = typer.Option(False, help="Enable debug, opening backtesting plot."),
    # Filename parameters
    filename: str = typer.Option(None, help="The name of the file to read the data from."),
):
    """
    Runs a backtest of the signal strategy for a symbol, using local data and configurable parameters.
    """
    symbol = symbol.strip().upper()
    filename = filename or get_default_candles_filename(symbol)
    # Create the config object from the CLI options
    try:
        df = load_candlestick_dataframe_from_file(filename)
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
            enable_exit_on_divergence_signal=sell_on_divergence,
            enable_exit_on_take_profit=enable_tp,
        )
        current_execution_result, bt, stats = backtesting_cli_service.execute_backtesting(
            exchange=exchange,
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
        typer.secho(
            f"❌ Error: Data file '{get_full_relative_path_by_filename(filename)}' not found.", fg=typer.colors.RED
        )
        typer.echo(f"👉 Please run 'cli download-data {symbol}' first.")
        raise typer.Exit()


@app.command()
def research(
    symbol: str = typer.Argument(..., help="The symbol to backtest, e.g., ETH/EUR"),
    initial_cash: float = typer.Option(3_000, help="Intial cash for the backtest."),
    exchange: str = typer.Option("mexc", help="The name of the exchange to use."),
    timeframe: str = typer.Option("1h", help="The timeframe to download data for."),
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
        in_sample_df = None
        out_of_sample_data_filename = f"{symbol.replace('/', '_')}_out_of_sample.csv"
        if from_parquet is None:
            in_sample_data_filename = f"{symbol.replace('/', '_')}_in_sample.csv"
            if download_candles:
                typer.echo("🍵 Downloading in-sample data...")
                download_data(
                    symbol=symbol,
                    exchange=exchange,
                    timeframe=timeframe,
                    months_back=DEFAULT_MONTHS_BACK,
                    months_offset=OUT_OF_SAMPLE_MONTHS_BACK,
                    filename=in_sample_data_filename,
                )
                typer.echo("🍵 Downloading out-of-sample data...")
                download_data(
                    symbol=symbol,
                    exchange=exchange,
                    timeframe=timeframe,
                    months_back=OUT_OF_SAMPLE_MONTHS_BACK,
                    months_offset=0,
                    filename=out_of_sample_data_filename,
                )
            in_sample_df = load_candlestick_dataframe_from_file(in_sample_data_filename)

        typer.secho("--- ⚙️ Research Parameters ---", fg=typer.colors.BLUE, bold=True)
        typer.echo(f"Symbol:                      {symbol}")
        typer.echo(f"Initial Cash:                {initial_cash}")
        typer.echo(f"Exchange:                    {exchange}")
        typer.echo(f"Timeframe:                   {timeframe}")
        typer.echo(f"In-Sample Months Back:       {DEFAULT_MONTHS_BACK}")
        typer.echo(f"Out-Sample Months Back:      {OUT_OF_SAMPLE_MONTHS_BACK}")
        typer.echo(f"Disable Minimal Trades:      {disable_minimal_trades}")
        typer.echo(f"Disable Decent Win Rate:     {disable_decent_win_rate}")
        typer.echo(f"Decent Win Rate Threshold:   {decent_win_rate}%")
        typer.echo(f"Min Profit Factor:           {min_profit_factor if min_profit_factor is not None else 'N/A'}")
        typer.echo(f"Min SQN:                     {min_sqn if min_sqn is not None else 'N/A'}")
        typer.echo(f"Take Profit Filter:          {tp_filter}")
        typer.echo(f"From Parquet:                {from_parquet if from_parquet is not None else 'No'}")
        typer.echo(f"Download Candles:            {download_candles}")
        typer.echo(f"Disable Progress Bar:        {disable_progress_bar}")
        typer.secho("-----------------------------", fg=typer.colors.BLUE, bold=True)

        execution_summary = backtesting_cli_service.find_out_best_parameters(
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
            in_sample_df=in_sample_df,
            out_of_sample_df=load_candlestick_dataframe_from_file(out_of_sample_data_filename),
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
                    echo_backtesting_in_out_of_sample_result(value)
    except FileNotFoundError as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.error(e)
        typer.secho("❌ Error: Data files not found.", fg=typer.colors.RED)
        typer.echo(f"👉 Please run 'cli download-data {symbol}' first.")
        raise typer.Exit()


if __name__ == "__main__":
    app()
