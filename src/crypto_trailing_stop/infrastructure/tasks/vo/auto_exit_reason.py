from dataclasses import dataclass


@dataclass(frozen=True)
class AutoExitReason:
    is_marked_for_immediate_sell: bool
    stop_loss_reached_at_closing_price: bool
    stop_loss_reached_at_current_price: bool
    exit_on_sell_signal: bool
    take_profit_reached: bool
    percent_to_sell: float = 100.0

    @property
    def stop_loss_triggered(self) -> bool:
        return self.stop_loss_reached_at_current_price or self.stop_loss_reached_at_closing_price

    @property
    def is_exit(self) -> bool:
        return (
            self.is_marked_for_immediate_sell
            or self.stop_loss_triggered
            or self.exit_on_sell_signal
            or self.take_profit_reached
        )
