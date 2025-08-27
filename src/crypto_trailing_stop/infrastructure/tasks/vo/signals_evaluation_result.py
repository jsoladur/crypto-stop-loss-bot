from dataclasses import dataclass, field

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
    def is_positive(self) -> bool:
        return self.is_buy_sell_signal or self.is_divergence_signal

    @property
    def is_buy_sell_signal(self) -> bool:
        return not self.is_choppy and (self.buy or self.sell)

    @property
    def is_divergence_signal(self) -> bool:
        return self.bearish_divergence or self.bullish_divergence

    @property
    def cache_key(self) -> str:
        return f"{self.symbol}_$$_{self.timeframe}"
