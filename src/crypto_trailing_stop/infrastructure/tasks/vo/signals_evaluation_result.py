from dataclasses import dataclass, field
from typing import Literal

from crypto_trailing_stop.commons.constants import (
    BUY_SELL_RELIABLE_TIMEFRAMES,
    DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE,
    NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL,
)
from crypto_trailing_stop.infrastructure.tasks.vo.types import Timeframe


@dataclass(frozen=True)
class SignalsEvaluationResult:
    timestamp: float | int
    symbol: str
    timeframe: Timeframe
    buy: bool
    sell: bool
    rsi_state: Literal["neutral", "overbought", "oversold"]
    is_choppy: bool
    # Additional info but no comparable
    atr: float = field(compare=False)
    closing_price: float = field(compare=False)
    ema_long_price: float = field(compare=False)

    @property
    def atr_percent(self) -> float:
        return round(
            (self.atr / self.closing_price) * 100,
            ndigits=NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(self.symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE),
        )

    @property
    def is_reliable(self) -> bool:
        return self.timeframe in BUY_SELL_RELIABLE_TIMEFRAMES

    @property
    def is_positive(self) -> bool:
        return not self.is_choppy and (self.buy or self.sell)

    @property
    def cache_key(self) -> str:
        return f"{self.symbol}_$$_{self.timeframe}"
