from dataclasses import dataclass
from typing import Literal

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
    def is_positive(self) -> bool:
        return self.buy or self.sell

    @property
    def cache_key(self) -> str:
        return f"{self.symbol}_$$_{self.timeframe}"
