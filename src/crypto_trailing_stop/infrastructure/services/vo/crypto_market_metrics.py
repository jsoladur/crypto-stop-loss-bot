from dataclasses import dataclass

from crypto_trailing_stop.commons.constants import (
    DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE,
    NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL,
)
from crypto_trailing_stop.config import get_configuration_properties
from crypto_trailing_stop.infrastructure.tasks.vo.types import RSIState


@dataclass
class CryptoMarketMetrics:
    symbol: str
    closing_price: float
    ema_short: float
    ema_mid: float
    ema_long: float
    rsi: float | int
    atr: float

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
