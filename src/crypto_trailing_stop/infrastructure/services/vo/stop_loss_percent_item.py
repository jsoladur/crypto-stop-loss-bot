from dataclasses import dataclass


@dataclass
class StopLossPercentItem:
    symbol: str
    value: float

    def __post_init__(self):
        self.symbol = self.symbol.strip().upper()
        if self.value < 0.25 or self.value > 10.0:  # pragma: no cover
            raise ValueError("Stop loss percent must be a value between 0.25 and 10.0")
