import os

import pandas as pd
import typer
from faker import Faker

from crypto_trailing_stop.scripts.constants import DEFAULT_BIT2ME_BASE_URL
from crypto_trailing_stop.scripts.services import BacktestingCliService

# ------------------------------------------------------------------------------------
# Mock env variables
# ------------------------------------------------------------------------------------

# .env.backtest
faker = Faker()
os.environ["TELEGRAM_BOT_TOKEN"] = f"{faker.pyint()}:{faker.uuid4().replace('-', '_')}"
os.environ["BIT2ME_API_BASE_URL"] = DEFAULT_BIT2ME_BASE_URL
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
    years_back: float = typer.Option(1.0, help="The number of years of data to download."),
):
    """
    Downloads the last 1 year of 1H historical data for a symbol and saves it to data/.
    """
    symbol = symbol.strip().upper()
    try:
        typer.secho(f"📥 Starting download for {symbol} on 1h timeframe...", fg=typer.colors.BLUE)
        all_ohlcv = backtesting_cli_service.download_backtesting_data(
            symbol, exchange, timeframe, years_back, echo_fn=typer.secho
        )
        typer.secho(f"✅ Download complete. {len(all_ohlcv)} candles fetched.", fg=typer.colors.GREEN)
        if all_ohlcv:
            df = pd.DataFrame(all_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            if not os.path.exists("data"):
                os.makedirs("data")
            filename = f"data/{symbol.replace('/', '_')}.csv"
            df.to_csv(filename, index=False)
            typer.echo(f"💾 Data saved to '{filename}'")
    except Exception as e:
        typer.secho(f"❌ Error downloading data: {e}", fg=typer.colors.RED)


@app.command()
def backtesting(
    symbol: str = typer.Argument(..., help="The symbol to backtest, e.g., ETH/EUR"),
    # EMA/ADX parameters
    ema_short: int = typer.Option(9, help="Length of the short EMA."),
    ema_mid: int = typer.Option(21, help="Length of the medium EMA."),
    ema_long: int = typer.Option(200, help="Length of the long EMA."),
    filter_adx: bool = typer.Option(True, help="Enable/disable the ADX noise filter."),
    adx_threshold: int = typer.Option(20, help="ADX threshold for trend confirmation."),
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
    typer.secho(f"⚙️  Starting backtest for {symbol} with the following parameters:", fg=typer.colors.BLUE)
    typer.echo(f"  - EMAs: {ema_short}/{ema_mid}/{ema_long}")
    typer.echo(
        f"  - ADX Filter: {'Enabled' if filter_adx else 'Disabled'}, Threshold: {adx_threshold if filter_adx else 'N/A'}"  # noqa: E501
    )
    # NEW: Print SL/TP settings
    typer.echo(f"  - Stop Loss Multiplier: {sl_multiplier}x ATR")
    typer.echo(
        f"  - Take Profit: {'Enabled' if enable_tp else 'Disabled'}, Multiplier: {tp_multiplier if enable_tp else 'N/A'}x ATR"  # noqa: E501
    )
    # Create the config object from the CLI options
    try:
        data_file = f"data/{symbol.replace('/', '_')}.csv"
        df = pd.read_csv(data_file)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.dropna(inplace=True)
        df.reset_index(drop=True, inplace=True)

        typer.echo(f"📊 {len(df)} candles loaded. Calculating indicators and signals...")

        bt, stats = backtesting_cli_service.execute_backtesting(
            symbol,
            ema_short,
            ema_mid,
            ema_long,
            filter_adx,
            adx_threshold,
            enable_tp,
            sl_multiplier,
            tp_multiplier,
            initial_cash,
            df,
            echo_fn=typer.secho,
        )

        if debug:
            if not os.path.exists("data"):
                os.makedirs("data")
            filename = f"data/{symbol.replace('/', '_')}_indicators.csv"
            df.to_csv(filename, index=False)
            typer.echo(f"💾 Indicators outcomes saved to '{filename}'")

        typer.secho("\n--- 📈 BACKTEST RESULTS ---", fg=typer.colors.MAGENTA, bold=True)
        typer.echo(stats)

        typer.secho("\n--- 📝 SUMMARY ---", fg=typer.colors.MAGENTA, bold=True)
        # Calculate the net profit/loss
        net_profit_loss = stats["Equity Final [$]"] - initial_cash
        # Style the output strings
        win_rate_str = typer.style(
            f"{stats['Win Rate [%]']:.2f}%", fg=typer.colors.GREEN if stats["Win Rate [%]"] > 50 else typer.colors.RED
        )
        return_eur_str = typer.style(
            f"{net_profit_loss:.2f} EUR", fg=typer.colors.GREEN if net_profit_loss > 0 else typer.colors.RED
        )
        return_pct_str = typer.style(
            f"{(stats['Return [%]']):.2f}%", fg=typer.colors.GREEN if stats["Return [%]"] > 0 else typer.colors.RED
        )

        typer.echo(f"Win Rate [%]:                {win_rate_str}")
        typer.echo(f"Net Profit/Loss [EUR]:       {return_eur_str}")
        typer.echo(f"Net Return [%]:              {return_pct_str}")

        if show_plot:
            bt.plot()
    except FileNotFoundError:
        typer.secho(f"❌ Error: Data file '{data_file}' not found.", fg=typer.colors.RED)
        typer.echo(f"👉 Please run 'python scripts/main.py download-data {symbol}' first.")
        raise typer.Exit()


if __name__ == "__main__":
    app()
