from dataclasses import dataclass
from typing import Literal

from crypto_trailing_stop.commons.constants import BUY_SELL_RELIABLE_TIMEFRAMES
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

    @property
    def is_reliable(self) -> bool:
        return self.timeframe in BUY_SELL_RELIABLE_TIMEFRAMES

    @property
    def is_positive(self) -> bool:
        return not self.is_choppy and (self.buy or self.sell)

    @property
    def cache_key(self) -> str:
        return f"{self.symbol}_$$_{self.timeframe}"
