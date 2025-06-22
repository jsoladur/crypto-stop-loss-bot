from dataclasses import dataclass


@dataclass
class StopLossPercentItem:
    symbol: str
    value: float

    def __post_init__(self):
        self.symbol = self.symbol.strip().upper()
        if self.value <= 1.0 or self.value >= 5.0:
            raise ValueError("Stop loss percent must be a value between 1.0 and 5.0")
