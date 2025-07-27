from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from crypto_trailing_stop.commons.constants import (
    DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE,
    NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL,
)
from crypto_trailing_stop.config import get_configuration_properties
from crypto_trailing_stop.infrastructure.tasks.vo.types import RSIState


@dataclass(frozen=True)
class CryptoMarketMetrics:
    symbol: str
    timestamp: datetime
    closing_price: float | int
    ema_short: float | int
    ema_mid: float | int
    ema_long: float | int
    macd_hist: float | int
    rsi: float | int
    atr: float | int
    adx: float | int
    adx_pos: float | int
    adx_neg: float | int

    is_rounded: bool

    @property
    def rsi_state(self) -> RSIState:
        configuration_properties = get_configuration_properties()
        main_trend_is_up = bool(self.closing_price > self.ema_long)
        if self.rsi > configuration_properties.buy_sell_signals_rsi_overbought:
            rsi_state = "bullish_momentum" if main_trend_is_up else "overbought"
        elif self.rsi < configuration_properties.buy_sell_signals_rsi_oversold:
            rsi_state = "oversold"
        else:
            rsi_state = "neutral"
        return rsi_state

    @property
    def atr_percent(self) -> float:
        return round(
            (self.atr / self.closing_price) * 100,
            ndigits=NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(self.symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE),
        )

    def rounded(self) -> "CryptoMarketMetrics":
        ret = self
        if not self.is_rounded:
            ndigits = NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(self.symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE)
            ret = CryptoMarketMetrics(
                symbol=self.symbol,
                timestamp=self.timestamp,
                closing_price=round(self.closing_price, ndigits=ndigits),
                ema_short=round(self.ema_short, ndigits=ndigits),
                ema_mid=round(self.ema_mid, ndigits=ndigits),
                ema_long=round(self.ema_long, ndigits=ndigits),
                macd_hist=round(self.macd_hist, ndigits=ndigits),
                rsi=round(self.rsi, ndigits=2),
                atr=round(self.atr, ndigits=ndigits),
                adx=round(self.adx, ndigits=2),
                adx_pos=round(self.adx_pos, ndigits=2),
                adx_neg=round(self.adx_neg, ndigits=2),
                is_rounded=True,
            )
        return ret

    @staticmethod
    def from_candlestick(symbol: str, candlestick: pd.Series, *, apply_round: bool = False) -> "CryptoMarketMetrics":
        ndigits = NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE)
        ret = CryptoMarketMetrics(
            symbol=symbol,
            timestamp=candlestick["timestamp"],
            closing_price=round(candlestick["close"], ndigits=ndigits) if apply_round else candlestick["close"],
            ema_short=round(candlestick["ema_short"], ndigits=ndigits) if apply_round else candlestick["ema_short"],
            ema_mid=round(candlestick["ema_mid"], ndigits=ndigits) if apply_round else candlestick["ema_mid"],
            ema_long=round(candlestick["ema_long"], ndigits=ndigits) if apply_round else candlestick["ema_long"],
            macd_hist=round(candlestick["macd_hist"], ndigits=ndigits) if apply_round else candlestick["macd_hist"],
            rsi=round(candlestick["rsi"], ndigits=2) if apply_round else candlestick["rsi"],
            atr=round(candlestick["atr"], ndigits=ndigits) if apply_round else candlestick["atr"],
            adx=round(candlestick["adx"], ndigits=2) if apply_round else candlestick["adx"],
            adx_pos=round(candlestick["adx_pos"], ndigits=2) if apply_round else candlestick["adx_pos"],
            adx_neg=round(candlestick["adx_neg"], ndigits=2) if apply_round else candlestick["adx_neg"],
            is_rounded=apply_round,
        )
        return ret
