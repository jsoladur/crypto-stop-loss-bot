from dataclasses import dataclass, field

from crypto_trailing_stop.commons.constants import ANTICIPATION_ZONE_TIMEFRAMES, BUY_SELL_RELIABLE_TIMEFRAMES
from crypto_trailing_stop.infrastructure.tasks.vo.types import RSIState, Timeframe


@dataclass(frozen=True)
class SignalsEvaluationResult:
    timestamp: float | int
    symbol: str
    timeframe: Timeframe
    buy: bool
    sell: bool
    rsi_state: RSIState
    is_choppy: bool
    # Bearish & Bullish divergence flags
    bearish_divergence: bool
    bullish_divergence: bool
    # Additional info but no comparable
    atr: float = field(compare=False)
    closing_price: float = field(compare=False)
    ema_long_price: float = field(compare=False)

    @property
    def is_reliable(self) -> bool:
        return self.timeframe in BUY_SELL_RELIABLE_TIMEFRAMES

    @property
    def is_anticipation_zone(self) -> bool:
        return self.timeframe in ANTICIPATION_ZONE_TIMEFRAMES

    @property
    def is_positive(self) -> bool:
        return not self.is_choppy and (self.buy or self.sell)

    @property
    def cache_key(self) -> str:
        return f"{self.symbol}_$$_{self.timeframe}"
