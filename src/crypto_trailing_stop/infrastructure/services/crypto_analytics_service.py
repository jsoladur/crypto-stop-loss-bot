import logging
from typing import Literal

import ccxt.async_support as ccxt  # Notice the async_support import
import pandas as pd
from httpx import AsyncClient
from ta.momentum import RSIIndicator
from ta.trend import MACD, EMAIndicator
from ta.volatility import AverageTrueRange

from crypto_trailing_stop.commons.patterns import SingletonMeta
from crypto_trailing_stop.config import get_configuration_properties
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.enums.candlestick_enum import CandleStickEnum
from crypto_trailing_stop.infrastructure.services.vo.crypto_market_metrics import CryptoMarketMetrics
from crypto_trailing_stop.infrastructure.tasks.vo.types import Timeframe

logger = logging.getLogger(__name__)


class CryptoAnalyticsService(metaclass=SingletonMeta):
    def __init__(self, bit2me_remote_service: Bit2MeRemoteService, ccxt_remote_service: CcxtRemoteService) -> None:
        self._configuration_properties = get_configuration_properties()
        self._bit2me_remote_service = bit2me_remote_service
        self._ccxt_remote_service = ccxt_remote_service

    async def get_crypto_market_metrics(
        self,
        symbol: str,
        *,
        timeframe: Timeframe = "1h",
        over_candlestick: CandleStickEnum = CandleStickEnum.LAST,
        exchange_client: ccxt.Exchange | None = None,
    ) -> CryptoMarketMetrics:
        technical_indicators: pd.DataFrame = await self.calculate_technical_indicators(
            symbol, timeframe=timeframe, exchange_client=exchange_client
        )
        selected_candlestick = technical_indicators.iloc[over_candlestick.value]
        return CryptoMarketMetrics(
            symbol=symbol,
            closing_price=selected_candlestick["close"],
            ema_short=selected_candlestick["ema_short"],
            ema_mid=selected_candlestick["ema_mid"],
            ema_long=selected_candlestick["ema_long"],
            rsi=selected_candlestick["rsi"],
            atr=selected_candlestick["atr"],
        )

    async def calculate_technical_indicators(
        self, symbol: str, *, timeframe: Timeframe = "1h", exchange_client: ccxt.Exchange | None = None
    ) -> pd.DataFrame:
        df = await self._ccxt_remote_service.fetch_ohlcv(symbol, timeframe, exchange_client=exchange_client)
        df_with_indicators = self._calculate_indicators(df)
        return df_with_indicators

    async def get_favourite_tickers(self) -> list[Bit2MeTickersDto]:
        async with await self._bit2me_remote_service.get_http_client() as client:
            favourite_symbols = await self.get_favourite_symbols(client=client)
            ret = [
                await self._bit2me_remote_service.get_tickers_by_symbol(symbol=symbol, client=client)
                for symbol in favourite_symbols
            ]
            return ret

    async def get_favourite_symbols(self, *, client: AsyncClient | None = None) -> list[str]:
        if client:
            ret = await self._internal_get_favourite_symbols(client=client)
        else:
            async with await self._bit2me_remote_service.get_http_client() as client:
                ret = await self._internal_get_favourite_symbols(client=client)
        return ret

    def get_exchange_client(self, *, exchange: Literal["binance"] = "binance") -> ccxt.Exchange:
        if exchange != "binance":  # pragma: no cover
            raise ValueError(f"Exchange '{exchange}' is not supported yet!")
        return self._ccxt_remote_service.get_binance_exchange_client()

    async def _internal_get_favourite_symbols(self, *, client: AsyncClient) -> list[str]:
        favourite_crypto_currencies = await self._bit2me_remote_service.get_favourite_crypto_currencies(client=client)
        bit2me_account_info = await self._bit2me_remote_service.get_account_info(client=client)
        symbols = [
            f"{crypto_currency}/{bit2me_account_info.profile.currency_code}"
            for crypto_currency in favourite_crypto_currencies
        ]
        return symbols

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.debug("Calculating indicators...")
        # Exponential Moving Average (EMA) 9
        df["ema_short"] = EMAIndicator(
            df["close"], window=self._configuration_properties.buy_sell_signals_ema_short_value
        ).ema_indicator()
        # Exponential Moving Average (EMA) 21
        df["ema_mid"] = EMAIndicator(
            df["close"], window=self._configuration_properties.buy_sell_signals_ema_mid_value
        ).ema_indicator()
        # Exponential Moving Average (EMA) 200
        df["ema_long"] = EMAIndicator(
            df["close"], window=self._configuration_properties.buy_sell_signals_ema_long_value
        ).ema_indicator()
        # Moving Average Convergence Divergence (MACD)
        macd = MACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
        df["macd_hist"] = macd.macd_diff()
        # Relative Strength Index (RSI)
        df["rsi"] = RSIIndicator(df["close"], window=14).rsi()
        # Average True Range (ATR)
        df["atr"] = AverageTrueRange(df["high"], df["low"], df["close"], window=14).average_true_range()
        df.dropna(inplace=True)
        df.reset_index(drop=True, inplace=True)
        logger.debug("Indicator calculation complete.")
        return df
