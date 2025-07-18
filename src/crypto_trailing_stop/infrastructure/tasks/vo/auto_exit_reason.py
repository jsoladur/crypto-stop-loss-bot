from dataclasses import dataclass


@dataclass(frozen=True)
class AutoExitReason:
    safeguard_stop_price_reached: bool
    auto_exit_sell_1h: bool
    atr_take_profit_limit_price_reached: bool

    @property
    def is_exit(self) -> bool:
        return self.safeguard_stop_price_reached or self.auto_exit_sell_1h or self.atr_take_profit_limit_price_reached
