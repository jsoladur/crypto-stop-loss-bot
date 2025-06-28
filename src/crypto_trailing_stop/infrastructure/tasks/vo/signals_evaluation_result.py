from dataclasses import dataclass
from typing import Literal


@dataclass
class SignalsEvaluationResult:
    timestamp: float | int
    symbol: str
    timeframe: Literal["4h", "1h"]
    buy: bool
    sell: bool
    rsi_state: Literal["neutral", "overbought", "oversold"]

    @property
    def cache_key(self) -> str:
        return f"{self.symbol}_$$_{self.timeframe}"
