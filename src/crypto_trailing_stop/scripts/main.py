# At the top of scripts/main.py
import os
from datetime import UTC, datetime, timedelta
from os import path

import ccxt
import pandas as pd
import typer
from backtesting import Backtest
from dotenv import load_dotenv
from tqdm import tqdm

from crypto_trailing_stop.commons.constants import BIT2ME_TAKER_FEES
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.infrastructure.tasks.buy_sell_signals_task_service import BuySellSignalsTaskService
from crypto_trailing_stop.scripts.constants import DEFAULT_TRADING_MARKET_CONFIG
from crypto_trailing_stop.scripts.strategy import SignalStrategy

load_dotenv(dotenv_path=path.realpath(path.join(path.dirname(__file__), ".env.backtesting")))

# ------------------------------------------------------------------------------------
# --- Typer CLI Application ---
# ------------------------------------------------------------------------------------

app = typer.Typer()

analytics_service = CryptoAnalyticsService(
    bit2me_remote_service=None, ccxt_remote_service=CcxtRemoteService(), buy_sell_signals_config_service=None
)
signal_service = BuySellSignalsTaskService()


@app.command()
def download_data(
    symbol: str = typer.Argument(..., help="The symbol to download, e.g., ETH/EUR"),
    exchange_name: str = typer.Option("binance", help="The name of the exchange to use."),
):
    """
    Downloads the last 1 year of 1H historical data for a symbol and saves it to data/.
    """
    typer.secho(f"📥 Starting download for {symbol} on 1h timeframe...", fg=typer.colors.BLUE)

    if not os.path.exists("data"):
        os.makedirs("data")

    start_date = (datetime.now(UTC) - timedelta(days=365)).strftime("%Y-%m-%d")
    exchange = getattr(ccxt, exchange_name)()
    since_timestamp = int(datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=UTC).timestamp() * 1000)
    all_ohlcv = []

    with tqdm(desc="Downloading data batches") as pbar:
        while True:
            try:
                ohlcv = exchange.fetch_ohlcv(symbol, "1h", since=since_timestamp, limit=1000)
                if not ohlcv:
                    break
                all_ohlcv.extend(ohlcv)
                since_timestamp = ohlcv[-1][0] + 1
                pbar.update(1)
            except Exception as e:
                typer.secho(f"❌ Error downloading data: {e}", fg=typer.colors.RED)
                break

    typer.secho(f"✅ Download complete. {len(all_ohlcv)} candles fetched.", fg=typer.colors.GREEN)
    if not all_ohlcv:
        return

    df = pd.DataFrame(all_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])

    filename = f"data/{symbol.replace('/', '_')}_1h.csv"
    df.to_csv(filename, index=False)
    typer.echo(f"💾 Data saved to '{filename}'")


@app.command()
def backtesting(
    symbol: str = typer.Argument(..., help="The symbol to backtest, e.g., ETH/EUR"),
    # EMA/ADX parameters
    ema_short: int = typer.Option(9, help="Length of the short EMA."),
    ema_mid: int = typer.Option(21, help="Length of the medium EMA."),
    ema_long: int = typer.Option(200, help="Length of the long EMA."),
    filter_adx: bool = typer.Option(True, help="Enable/disable the ADX noise filter."),
    adx_threshold: int = typer.Option(20, help="ADX threshold for trend confirmation."),
    initial_cash: float = typer.Option(3_000, help="Intial cash for the backtest."),
    enable_tp: bool = typer.Option(False, "--enable-tp", help="Enable the ATR-based Take Profit."),
    sl_multiplier: float = typer.Option(2.5, help="ATR multiplier for Stop Loss."),
    tp_multiplier: float = typer.Option(3.5, help="ATR multiplier for Take Profit."),
    debug: bool = typer.Option(False, help="Enable debug, opening backtesting plot."),
):
    """
    Runs a backtest of the signal strategy for a symbol, using local data and configurable parameters.
    """
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
        simulated_bs_config = BuySellSignalsConfigItem(
            symbol=symbol,
            ema_short_value=ema_short,
            ema_mid_value=ema_mid,
            ema_long_value=ema_long,
            adx_threshold=adx_threshold,
            filter_noise_using_adx=filter_adx,
        )
        data_file = f"data/{symbol.replace('/', '_')}_1h.csv"
        df = pd.read_csv(data_file)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)

        typer.echo(f"📊 {len(df)} candles loaded. Calculating indicators and signals...")

        analytics_service._calculate_simple_indicators(df, simulated_bs_config)
        analytics_service._calculate_complex_indicators(df)
        df.dropna(inplace=True)
        df.reset_index(drop=True, inplace=True)

        buy_signals = []
        sell_signals = []

        typer.echo("🧠 Generating signals for each historical candle...")
        for i in tqdm(range(4, len(df))):
            window_df = df.iloc[: i + 1]
            signals = signal_service._check_signals(
                symbol=symbol,
                timeframe="1h",
                df=window_df,
                buy_sell_signals_config=simulated_bs_config,
                trading_market_config=DEFAULT_TRADING_MARKET_CONFIG,
            )
            buy_signals.append(signals.buy)
            sell_signals.append(signals.sell)

        df["buy_signal"] = pd.Series(buy_signals, index=df.index[4:])
        df["sell_signal"] = pd.Series(sell_signals, index=df.index[4:])
        # NEW: Add previous MACD hist for the accelerating momentum check
        df["prev_macd_hist"] = df["macd_hist"].shift(1)
        df.fillna(False, inplace=True)

        typer.secho("🚀 Running trading simulation...", fg=typer.colors.CYAN)
        df.rename(
            columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True
        )
        bt = Backtest(df, SignalStrategy, cash=initial_cash, commission=BIT2ME_TAKER_FEES)
        stats = bt.run(
            enable_tp=enable_tp,
            atr_sl_multiplier=sl_multiplier,
            atr_tp_multiplier=tp_multiplier,
            simulated_bs_config=simulated_bs_config,
            analytics_service=analytics_service,
        )
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

        if debug:
            bt.plot()
    except FileNotFoundError:
        typer.secho(f"❌ Error: Data file '{data_file}' not found.", fg=typer.colors.RED)
        typer.echo(f"👉 Please run 'python scripts/main.py download-data {symbol}' first.")
        raise typer.Exit()


if __name__ == "__main__":
    app()
