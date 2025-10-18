from dataclasses import dataclass, field


@dataclass
class GlobalSummary:
    """
    Represents a global summary of Operating Exchange cryptocurrency portfolio.
    """

    total_deposits: float = field(default=0.0)
    withdrawls: float = field(default=0.0)
    current_value: float = field(default=0.0)

    @property
    def total_invested(self) -> float:
        return self.total_deposits - self.withdrawls

    @property
    def net_revenue(self) -> float:
        return (self.current_value - self.total_deposits) + self.withdrawls
