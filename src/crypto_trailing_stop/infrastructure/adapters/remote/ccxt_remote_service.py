import logging
from typing import Any

import backoff
import cachebox
import ccxt.async_support as ccxt

from crypto_trailing_stop.commons.constants import DEFAULT_IN_MEMORY_CACHE_TTL_IN_SECONDS
from crypto_trailing_stop.infrastructure.tasks.vo.types import Timeframe

logger = logging.getLogger(__name__)


class CcxtRemoteService:
    @backoff.on_exception(
        backoff.constant,
        exception=ccxt.BaseError,
        interval=2,
        max_tries=5,
        jitter=backoff.full_jitter,
        giveup=lambda e: isinstance(e, ccxt.BadRequest) or isinstance(e, ccxt.AuthenticationError),
        on_backoff=lambda details: logger.warning(
            f"[Retry {details['tries']}] " + f"Waiting {details['wait']:.2f}s due to {str(details['exception'])}"
        ),
    )
    async def fetch_ohlcv(
        self, symbol: str, timeframe: Timeframe, limit: int = 251, *, exchange: ccxt.Exchange | None = None
    ) -> list[list[Any]]:
        """Fetches OHLCV data.

        Args:
            symbol (str): The trading symbol (e.g., 'ETH/EUR')
            timeframe (Timeframe): The timeframe (e.g., '1h', '4h')
            limit (int, optional): The number of candles to fetch. Defaults to 251 to have enough data
                   for a 200-period indicator after dropping the current, live candle. Defaults to 251.
            exchange (ccxt.Exchange | None, optional): Exchange client. Defaults to None.

        Returns:
            list[list[Any]]: OHLCV data
        """
        logger.info(f"Fetching {limit} {timeframe} bars for {symbol}...")
        # Fetch N+1 candles to account for the live one.
        if exchange:
            ohlcv = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        else:
            async with self.get_exchange() as exchange:
                ohlcv = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        return ohlcv

    @cachebox.cachedmethod(
        cachebox.TTLCache(0, ttl=DEFAULT_IN_MEMORY_CACHE_TTL_IN_SECONDS),
        key_maker=lambda _, kwds: kwds["fiat_currency"],
    )
    @backoff.on_exception(
        backoff.constant,
        exception=ccxt.BaseError,
        interval=2,
        max_tries=5,
        jitter=backoff.full_jitter,
        giveup=lambda e: isinstance(e, ccxt.BadRequest) or isinstance(e, ccxt.AuthenticationError),
        on_backoff=lambda details: logger.warning(
            f"[Retry {details['tries']}] " + f"Waiting {details['wait']:.2f}s due to {str(details['exception'])}"
        ),
    )
    async def get_exchange_symbols_by_fiat_currency(
        self, fiat_currency: str = "EUR", *, exchange: ccxt.Exchange | None = None
    ) -> list[str]:
        if exchange:
            markets = await exchange.load_markets()
        else:
            async with self.get_exchange() as exchange:
                markets = await exchange.load_markets()
        ret = [
            market["symbol"]
            for market in markets.values()
            if str(market["quote"]).upper() == str(fiat_currency).upper()
        ]
        return ret

    def get_exchange(self) -> ccxt.Exchange:
        exchange = ccxt.binance()
        return exchange
