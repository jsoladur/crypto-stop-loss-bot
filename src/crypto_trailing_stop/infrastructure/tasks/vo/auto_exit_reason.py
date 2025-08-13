from dataclasses import dataclass


@dataclass(frozen=True)
class AutoExitReason:
    is_marked_for_immediate_sell: bool
    safeguard_stop_price_reached: bool
    auto_exit_sell_1h: bool
    atr_take_profit_limit_price_reached: bool
    percent_to_sell: float = 100.0

    @property
    def is_exit(self) -> bool:
        return (
            self.is_marked_for_immediate_sell
            or self.safeguard_stop_price_reached
            or self.auto_exit_sell_1h
            or self.atr_take_profit_limit_price_reached
        )
