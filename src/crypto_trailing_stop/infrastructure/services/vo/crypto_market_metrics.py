from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_market_config_dto import Bit2MeMarketConfigDto
from crypto_trailing_stop.infrastructure.tasks.vo.types import RSIState


@dataclass(frozen=True)
class CryptoMarketMetrics:
    symbol: str
    timestamp: datetime
    highest_price: float | int
    lowest_price: float | int
    opening_price: float | int
    closing_price: float | int
    ema_short: float | int
    ema_mid: float | int
    ema_long: float | int
    macd_signal: float | int
    macd_line: float | int
    macd_hist: float | int
    rsi: float | int
    atr: float | int
    atr_percent: float | int
    adx: float | int
    adx_pos: float | int
    adx_neg: float | int
    bb_upper: float | int
    bb_middle: float | int
    bb_lower: float | int
    relative_vol: float | int
    # Bearish & Bullish divergence flags
    bearish_divergence: bool
    bullish_divergence: bool
    is_rounded: bool

    @property
    def rsi_state(self) -> RSIState:
        from crypto_trailing_stop.config.dependencies import get_application_container

        configuration_properties = get_application_container().configuration_properties()
        main_trend_is_up = bool(self.closing_price > self.ema_long)
        if self.rsi > configuration_properties.buy_sell_signals_rsi_overbought:
            rsi_state = "bullish_momentum" if main_trend_is_up else "overbought"
        elif self.rsi < configuration_properties.buy_sell_signals_rsi_oversold:
            rsi_state = "oversold"
        else:
            rsi_state = "neutral"
        return rsi_state

    def rounded(self, trading_market_config: Bit2MeMarketConfigDto) -> "CryptoMarketMetrics":
        ret = self
        if not self.is_rounded:
            ndigits = trading_market_config.price_precision
            ret = CryptoMarketMetrics(
                symbol=self.symbol,
                timestamp=self.timestamp,
                highest_price=round(self.highest_price, ndigits=ndigits),
                lowest_price=round(self.lowest_price, ndigits=ndigits),
                opening_price=round(self.opening_price, ndigits=ndigits),
                closing_price=round(self.closing_price, ndigits=ndigits),
                ema_short=round(self.ema_short, ndigits=ndigits),
                ema_mid=round(self.ema_mid, ndigits=ndigits),
                ema_long=round(self.ema_long, ndigits=ndigits),
                macd_signal=round(self.macd_signal, ndigits=ndigits),
                macd_line=round(self.macd_line, ndigits=ndigits),
                macd_hist=round(self.macd_hist, ndigits=ndigits),
                rsi=round(self.rsi, ndigits=2),
                atr=round(self.atr, ndigits=ndigits),
                atr_percent=round(self.atr_percent, ndigits=ndigits),
                adx=round(self.adx, ndigits=2),
                adx_pos=round(self.adx_pos, ndigits=2),
                adx_neg=round(self.adx_neg, ndigits=2),
                bb_upper=round(self.bb_upper, ndigits=ndigits),
                bb_middle=round(self.bb_middle, ndigits=ndigits),
                bb_lower=round(self.bb_lower, ndigits=ndigits),
                relative_vol=round(self.relative_vol, ndigits=2),
                bearish_divergence=self.bearish_divergence,
                bullish_divergence=self.bullish_divergence,
                is_rounded=True,
            )
        return ret

    @staticmethod
    def from_candlestick(
        symbol: str, candlestick: pd.Series, *, trading_market_config: Bit2MeMarketConfigDto, apply_round: bool = False
    ) -> "CryptoMarketMetrics":
        ndigits = trading_market_config.price_precision
        atr_percent = (candlestick["atr"] / candlestick["close"]) * 100
        ret = CryptoMarketMetrics(
            symbol=symbol,
            timestamp=candlestick["timestamp"],
            highest_price=round(candlestick["high"], ndigits=ndigits) if apply_round else candlestick["high"],
            lowest_price=round(candlestick["low"], ndigits=ndigits) if apply_round else candlestick["low"],
            opening_price=round(candlestick["open"], ndigits=ndigits) if apply_round else candlestick["open"],
            closing_price=round(candlestick["close"], ndigits=ndigits) if apply_round else candlestick["close"],
            ema_short=round(candlestick["ema_short"], ndigits=ndigits) if apply_round else candlestick["ema_short"],
            ema_mid=round(candlestick["ema_mid"], ndigits=ndigits) if apply_round else candlestick["ema_mid"],
            ema_long=round(candlestick["ema_long"], ndigits=ndigits) if apply_round else candlestick["ema_long"],
            macd_signal=round(candlestick["macd_signal"], ndigits=ndigits)
            if apply_round
            else candlestick["macd_signal"],
            macd_line=round(candlestick["macd_line"], ndigits=ndigits) if apply_round else candlestick["macd_line"],
            macd_hist=round(candlestick["macd_hist"], ndigits=ndigits) if apply_round else candlestick["macd_hist"],
            rsi=round(candlestick["rsi"], ndigits=2) if apply_round else candlestick["rsi"],
            atr=round(candlestick["atr"], ndigits=ndigits) if apply_round else candlestick["atr"],
            atr_percent=round(atr_percent, ndigits=ndigits) if apply_round else atr_percent,
            adx=round(candlestick["adx"], ndigits=2) if apply_round else candlestick["adx"],
            adx_pos=round(candlestick["adx_pos"], ndigits=2) if apply_round else candlestick["adx_pos"],
            adx_neg=round(candlestick["adx_neg"], ndigits=2) if apply_round else candlestick["adx_neg"],
            bb_upper=round(candlestick["bb_upper"], ndigits=ndigits) if apply_round else candlestick["bb_upper"],
            bb_middle=round(candlestick["bb_middle"], ndigits=ndigits) if apply_round else candlestick["bb_middle"],
            bb_lower=round(candlestick["bb_lower"], ndigits=ndigits) if apply_round else candlestick["bb_lower"],
            relative_vol=round(candlestick["relative_vol"], ndigits=2) if apply_round else candlestick["relative_vol"],
            bearish_divergence=candlestick["bearish_divergence"],
            bullish_divergence=candlestick["bullish_divergence"],
            is_rounded=apply_round,
        )
        return ret
