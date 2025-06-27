import ccxt
import logging
from pandas import pd

logger = logging.getLogger(__name__)


class CcxtRemoteService:
    def __init__(self):
        self._exchange = ccxt.binance()

    def fetch_ohlcv(
        self, symbol: str, timeframe: str, limit: int = 250
    ) -> pd.DataFrame:
        logger.info(f"Fetching {limit} {timeframe} bars for {symbol}...")
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(
            ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        print("Fetch complete.")
        return df
