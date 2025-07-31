import logging

import ccxt.async_support as ccxt
import pandas as pd
from httpx import AsyncClient
from ta.momentum import RSIIndicator
from ta.trend import MACD, ADXIndicator, EMAIndicator
from ta.volatility import AverageTrueRange, BollingerBands

from crypto_trailing_stop.commons.patterns import SingletonMeta
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.enums.candlestick_enum import CandleStickEnum
from crypto_trailing_stop.infrastructure.services.vo.buy_sell_signals_config_item import BuySellSignalsConfigItem
from crypto_trailing_stop.infrastructure.services.vo.crypto_market_metrics import CryptoMarketMetrics
from crypto_trailing_stop.infrastructure.tasks.vo.types import Timeframe

logger = logging.getLogger(__name__)


class CryptoAnalyticsService(metaclass=SingletonMeta):
    def __init__(
        self,
        bit2me_remote_service: Bit2MeRemoteService,
        ccxt_remote_service: CcxtRemoteService,
        buy_sell_signals_config_service: BuySellSignalsConfigService,
    ) -> None:
        self._bit2me_remote_service = bit2me_remote_service
        self._ccxt_remote_service = ccxt_remote_service
        self._buy_sell_signals_config_service = buy_sell_signals_config_service
        self._exchange = self._ccxt_remote_service.get_exchange()

    async def get_crypto_market_metrics(
        self,
        symbol: str,
        *,
        timeframe: Timeframe = "1h",
        over_candlestick: CandleStickEnum = CandleStickEnum.LAST,
        client: AsyncClient | None = None,
        exchange: ccxt.Exchange | None = None,
    ) -> CryptoMarketMetrics:
        technical_indicators, *_ = await self.calculate_technical_indicators(
            symbol, timeframe=timeframe, client=client, exchange=exchange
        )
        trading_market_config = await self._bit2me_remote_service.get_trading_market_config_by_symbol(
            symbol, client=client
        )
        selected_candlestick = technical_indicators.iloc[over_candlestick.value]
        ret = CryptoMarketMetrics.from_candlestick(
            symbol, selected_candlestick, trading_market_config=trading_market_config, apply_round=True
        )
        return ret

    async def calculate_technical_indicators(
        self,
        symbol: str,
        *,
        timeframe: Timeframe = "1h",
        client: AsyncClient | None = None,
        exchange: ccxt.Exchange | None = None,
    ) -> tuple[pd.DataFrame, BuySellSignalsConfigItem]:
        exchange = exchange or self._exchange
        exchange_symbols = await self._ccxt_remote_service.get_exchange_symbols_by_fiat_currency(
            fiat_currency=symbol.split("/")[-1], exchange=exchange
        )
        if symbol in exchange_symbols:
            ohlcv = await self._ccxt_remote_service.fetch_ohlcv(symbol, timeframe, exchange=exchange)
        else:
            ohlcv = await self._bit2me_remote_service.fetch_ohlcv(symbol, timeframe, client=client)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df_with_indicators, buy_sell_signals_config = await self._calculate_indicators(symbol, df)
        return df_with_indicators, buy_sell_signals_config

    async def get_favourite_tickers(self, *, client: AsyncClient | None = None) -> list[Bit2MeTickersDto]:
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

    async def _internal_get_favourite_symbols(self, *, client: AsyncClient) -> list[str]:
        favourite_crypto_currencies = await self._bit2me_remote_service.get_favourite_crypto_currencies(client=client)
        bit2me_account_info = await self._bit2me_remote_service.get_account_info(client=client)
        symbols = {
            f"{crypto_currency}/{bit2me_account_info.profile.currency_code}"
            for crypto_currency in favourite_crypto_currencies
        }
        # XXX: [JMSOLA] Include also as temporal favourite symbols those symbols we have positive balance
        trading_wallet_balances = await self._bit2me_remote_service.get_trading_wallet_balances(client=client)
        symbols.update(
            {
                f"{trading_wallet_balance.currency}/{bit2me_account_info.profile.currency_code}"
                for trading_wallet_balance in trading_wallet_balances
                if trading_wallet_balance.currency.lower() != bit2me_account_info.profile.currency_code.lower()
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
        # NEW: Calculate Bollinger Bands (BBands)
        bbands_indicator = BollingerBands(close=df["close"], window=20, window_dev=2)
        df["bb_upper"] = bbands_indicator.bollinger_hband()
        df["bb_middle"] = bbands_indicator.bollinger_mavg()
        df["bb_lower"] = bbands_indicator.bollinger_lband()
        # Drop NaN values
        df.dropna(inplace=True)
        df.reset_index(drop=True, inplace=True)
        logger.debug("Indicator calculation complete.")
        return df, buy_sell_signals_config
