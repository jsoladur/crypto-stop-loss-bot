import logging

import ccxt.async_support as ccxt  # Notice the async_support import
import pandas as pd

logger = logging.getLogger(__name__)


class CcxtRemoteService:
    def __init__(self):
        self._exchange = ccxt.binance()

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 251) -> pd.DataFrame:
        """
        Fetches OHLCV data.

        Args:
            symbol: The trading symbol (e.g., 'BTC/USDT').
            timeframe: The timeframe (e.g., '1h', '4h').
            limit: The number of candles to fetch. Defaults to 251 to have enough data
                   for a 200-period indicator after dropping the current, live candle.
        """
        logger.info(f"Fetching {limit} {timeframe} bars for {symbol}...")
        # Fetch N+1 candles to account for the live one.
        ohlcv = await self._exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df
