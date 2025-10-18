import logging
from typing import Any

import backoff
import ccxt.async_support as ccxt
import pandas as pd
import pydash
from ta.momentum import RSIIndicator
from ta.trend import MACD, ADXIndicator, EMAIndicator
from ta.volatility import AverageTrueRange, BollingerBands

from crypto_trailing_stop.commons.constants import DEFAULT_DIVERGENCE_WINDOW
from crypto_trailing_stop.commons.utils import backoff_on_backoff_handler
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange import AbstractOperatingExchangeService
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.vo.symbol_tickers import SymbolTickers
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.enums.candlestick_enum import CandleStickEnum
from crypto_trailing_stop.infrastructure.services.favourite_crypto_currency_service import (
    FavouriteCryptoCurrencyService,
)
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.infrastructure.services.vo.crypto_market_metrics import CryptoMarketMetrics
from crypto_trailing_stop.infrastructure.tasks.vo.types import Timeframe

logger = logging.getLogger(__name__)


class CryptoAnalyticsService:
    def __init__(
        self,
        operating_exchange_service: AbstractOperatingExchangeService,
        ccxt_remote_service: CcxtRemoteService,
        favourite_crypto_currency_service: FavouriteCryptoCurrencyService,
        buy_sell_signals_config_service: BuySellSignalsConfigService,
    ) -> None:
        self._operating_exchange_service = operating_exchange_service
        self._ccxt_remote_service = ccxt_remote_service
        self._favourite_crypto_currency_service = favourite_crypto_currency_service
        self._buy_sell_signals_config_service = buy_sell_signals_config_service
        self._exchange = self._ccxt_remote_service.get_exchange()

    async def get_crypto_market_metrics(
        self,
        symbol: str,
        *,
        timeframe: Timeframe = "1h",
        over_candlestick: CandleStickEnum = CandleStickEnum.LAST,
        technical_indicators: pd.DataFrame | None = None,
        client: Any | None = None,
        exchange: ccxt.Exchange | None = None,
    ) -> CryptoMarketMetrics:
        if technical_indicators is None:
            technical_indicators, *_ = await self.calculate_technical_indicators(
                symbol, timeframe=timeframe, client=client, exchange=exchange
            )
        trading_market_config = await self._operating_exchange_service.get_trading_market_config_by_symbol(
            symbol, client=client
        )
        selected_candlestick = technical_indicators.iloc[over_candlestick.value]
        ret = CryptoMarketMetrics.from_candlestick(
            symbol, selected_candlestick, trading_market_config=trading_market_config, apply_round=True
        )
        return ret

    # XXX: [JMSOLA] Add backoff to retry when no OHLCV data returned
    @backoff.on_exception(
        backoff.fibo,
        exception=IndexError,
        max_value=5,
        max_tries=7,
        jitter=backoff.random_jitter,
        on_backoff=backoff_on_backoff_handler,
    )
    async def calculate_technical_indicators(
        self,
        symbol: str,
        *,
        timeframe: Timeframe = "1h",
        client: Any | None = None,
        exchange: ccxt.Exchange | None = None,
    ) -> tuple[pd.DataFrame, BuySellSignalsConfigItem]:
        exchange = exchange or self._exchange
        exchange_symbols = await self._ccxt_remote_service.get_exchange_symbols_by_fiat_currency(
            fiat_currency=symbol.split("/")[-1], exchange=exchange
        )
        if symbol in exchange_symbols:
            ohlcv = await self._ccxt_remote_service.fetch_ohlcv(symbol, timeframe, exchange=exchange)
        else:
            ohlcv = await self._operating_exchange_service.fetch_ohlcv(symbol, timeframe, client=client)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df_with_indicators, buy_sell_signals_config = await self._calculate_indicators(symbol, df)
        return df_with_indicators, buy_sell_signals_config

    async def get_favourite_tickers(
        self, *, order_by_symbol: bool = False, client: Any | None = None
    ) -> list[SymbolTickers]:
        favourite_symbols = await self.get_favourite_symbols(client=client)
        ret = await self._operating_exchange_service.get_tickers_by_symbols(symbols=favourite_symbols, client=client)
        if order_by_symbol:
            ret = pydash.order_by(ret, ["symbol"])
        return ret

    async def get_favourite_symbols(self, *, client: Any | None = None) -> list[str]:
        if client:
            ret = await self._internal_get_favourite_symbols(client=client)
        else:
            async with await self._operating_exchange_service.get_client() as client:
                ret = await self._internal_get_favourite_symbols(client=client)
        return ret

    async def _internal_get_favourite_symbols(self, *, client: Any) -> list[str]:
        favourite_crypto_currencies = await self._favourite_crypto_currency_service.find_all()
        account_info = await self._operating_exchange_service.get_account_info(client=client)
        symbols = {f"{crypto_currency}/{account_info.currency_code}" for crypto_currency in favourite_crypto_currencies}
        # XXX: [JMSOLA] Include also as temporal favourite symbols those symbols we have positive balance
        trading_wallet_balances = await self._operating_exchange_service.get_trading_wallet_balances(client=client)
        symbols.update(
            {
                f"{trading_wallet_balance.currency}/{account_info.currency_code}"
                for trading_wallet_balance in trading_wallet_balances
                if trading_wallet_balance.currency.lower() != account_info.currency_code.lower()
                and trading_wallet_balance.is_effective
            }
        )
        return sorted(set(symbols))

    async def _calculate_indicators(
        self, symbol: str, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, BuySellSignalsConfigItem]:
        logger.debug("Calculating indicators...")
        crypto_currency, *_ = symbol.split("/")
        buy_sell_signals_config = await self._buy_sell_signals_config_service.find_by_symbol(crypto_currency)
        # 1. Calculate simple 'ta' indicators first
        self._calculate_simple_indicators(df, buy_sell_signals_config)
        # 2. Calculate complex indicators on the DataFrame.
        # This ensures the long lookback for divergence has enough data to work with.
        self._calculate_complex_indicators(df)
        # 3. NOW, drop NaN values and reset the index.
        # This cleans the data from the shorter lookback periods of the simple indicators.
        df.dropna(inplace=True)
        df.reset_index(drop=True, inplace=True)
        logger.debug("Indicator calculation complete.")
        return df, buy_sell_signals_config

    def _calculate_simple_indicators(self, df: pd.DataFrame, buy_sell_signals_config: BuySellSignalsConfigItem) -> None:
        # Exponential Moving Average (EMA) 9
        df["ema_short"] = EMAIndicator(df["close"], window=buy_sell_signals_config.ema_short_value).ema_indicator()
        # Exponential Moving Average (EMA) 21
        df["ema_mid"] = EMAIndicator(df["close"], window=buy_sell_signals_config.ema_mid_value).ema_indicator()
        # Exponential Moving Average (EMA) 200
        df["ema_long"] = EMAIndicator(df["close"], window=buy_sell_signals_config.ema_long_value).ema_indicator()
        # Moving Average Convergence Divergence (MACD)
        macd = MACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
        df["macd_line"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()
        df["macd_hist"] = macd.macd_diff()
        # Relative Strength Index (RSI)
        df["rsi"] = RSIIndicator(df["close"], window=14).rsi()
        # Average True Range (ATR)
        df["atr"] = AverageTrueRange(df["high"], df["low"], df["close"], window=14).average_true_range()
        # Calculate Average Directional Index (ADX)
        adx_indicator = ADXIndicator(high=df["high"], low=df["low"], close=df["close"], window=14)
        df["adx"] = adx_indicator.adx()
        df["adx_pos"] = adx_indicator.adx_pos()
        df["adx_neg"] = adx_indicator.adx_neg()
        # Calculate Bollinger Bands (BBands)
        bbands_indicator = BollingerBands(close=df["close"], window=20, window_dev=2)
        df["bb_upper"] = bbands_indicator.bollinger_hband()
        df["bb_middle"] = bbands_indicator.bollinger_mavg()
        df["bb_lower"] = bbands_indicator.bollinger_lband()
        # Calculate Relative Volume (RVOL)
        df["volume_sma"] = df["volume"].rolling(window=20).mean()
        df["relative_vol"] = df["volume"] / df["volume_sma"]

    def _calculate_complex_indicators(self, df: pd.DataFrame) -> None:
        """
        Calculates complex, window-based indicators like bearish divergence.
        """
        self._calculate_bearish_divergence(df)
        self._calculate_bullish_divergence(df)

    def _calculate_bearish_divergence(
        self, df: pd.DataFrame, *, divergence_window: int = DEFAULT_DIVERGENCE_WINDOW
    ) -> None:
        if len(df) >= divergence_window:
            # Find the highest high price in the lookback window
            df["highest_in_window"] = df["high"].rolling(window=divergence_window).max()
            # Find the index label of that highest high for each window.
            highest_in_window_idx = df["high"].rolling(window=divergence_window).apply(lambda x: x.idxmax(), raw=False)
            # Look up the RSI value using the found index label.
            df["rsi_at_highest"] = highest_in_window_idx.map(df["rsi"])
            # The divergence exists if the current high is at the window's high, but the RSI is lower
            df["bearish_divergence"] = (df["high"] >= df["highest_in_window"]) & (df["rsi"] < df["rsi_at_highest"])
            # Drop intermediate helper columns
            df.drop(columns=["highest_in_window", "rsi_at_highest"], inplace=True)
        else:
            df["bearish_divergence"] = False

    def _calculate_bullish_divergence(
        self, df: pd.DataFrame, *, divergence_window: int = DEFAULT_DIVERGENCE_WINDOW
    ) -> None:
        if len(df) >= divergence_window:
            # Find the lowest low price in the lookback window
            df["lowest_in_window"] = df["low"].rolling(window=divergence_window).min()
            # Find the index label of that lowest low for each window.
            lowest_in_window_idx = df["low"].rolling(window=divergence_window).apply(lambda x: x.idxmin(), raw=False)
            # Look up the RSI value using the found index label.
            df["rsi_at_lowest"] = lowest_in_window_idx.map(df["rsi"])
            # The divergence exists if the current low is at the window's low, but the RSI is higher
            df["bullish_divergence"] = (df["low"] <= df["lowest_in_window"]) & (df["rsi"] > df["rsi_at_lowest"])
            # Drop intermediate helper columns
            df.drop(columns=["lowest_in_window", "rsi_at_lowest"], inplace=True)
        else:
            df["bullish_divergence"] = False
