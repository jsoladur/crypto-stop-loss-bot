from dataclasses import dataclass


@dataclass(frozen=True)
class AutoExitReason:
    is_marked_for_immediate_sell: bool
    safeguard_stop_price_reached: bool
    exit_on_sell_signal: bool
    take_profit_reached: bool
    percent_to_sell: float = 100.0

    @property
    def is_exit(self) -> bool:
        return (
            self.is_marked_for_immediate_sell
            or self.safeguard_stop_price_reached
            or self.exit_on_sell_signal
            or self.take_profit_reached
        )
