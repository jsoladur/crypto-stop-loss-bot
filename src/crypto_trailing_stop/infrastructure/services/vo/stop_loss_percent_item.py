from dataclasses import dataclass

from crypto_trailing_stop.commons.constants import STOP_LOSS_ALLOWED_VALUES_LIST


@dataclass
class StopLossPercentItem:
    symbol: str
    value: float

    def __post_init__(self):
        min_value_allowed = STOP_LOSS_ALLOWED_VALUES_LIST[0]
        max_value_allowed = STOP_LOSS_ALLOWED_VALUES_LIST[-1]
        if self.value < min_value_allowed or self.value > max_value_allowed:  # pragma: no cover
            raise ValueError("Stop loss percent must be a value between 0.25 and 20.0")
        self.symbol = self.symbol.strip().upper()
