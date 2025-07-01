import logging

import backoff
import ccxt.async_support as ccxt  # Notice the async_support import
import pandas as pd

logger = logging.getLogger(__name__)


class CcxtRemoteService:
    async def fetch_ohlcv(
        self, symbol: str, timeframe: str, limit: int = 251, exchange_client: ccxt.Exchange | None = None
    ) -> pd.DataFrame:
        """
        Fetches OHLCV data.

        Args:
            symbol: The trading symbol (e.g., 'BTC/USDT').
            timeframe: The timeframe (e.g., '1h', '4h').
            limit: The number of candles to fetch. Defaults to 251 to have enough data
                   for a 200-period indicator after dropping the current, live candle.
        """
        if exchange_client:
            ret = await self._internal_fetch_ohlcv(symbol, timeframe, limit, exchange_client=exchange_client)
        else:  # pragma: no cover
            async with ccxt.binance() as exchange_client:
                ret = await self._internal_fetch_ohlcv(symbol, timeframe, limit, exchange_client=exchange_client)
        return ret

    @backoff.on_exception(
        backoff.constant,
        exception=ccxt.BaseError,
        interval=2,
        max_tries=5,
        jitter=backoff.full_jitter,
        on_backoff=lambda details: logger.warning(
            f"[Retry {details['tries']}] " + f"Waiting {details['wait']:.2f}s due to {str(details['exception'])}"
        ),
    )
    async def _internal_fetch_ohlcv(
        self, symbol: str, timeframe: str, limit: int = 251, *, exchange_client: ccxt.Exchange
    ) -> pd.DataFrame:
        logger.info(f"Fetching {limit} {timeframe} bars for {symbol}...")
        # Fetch N+1 candles to account for the live one.
        ohlcv = await exchange_client.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df

    def get_binance_exchange_client(self) -> ccxt.Exchange:
        return ccxt.binance()
