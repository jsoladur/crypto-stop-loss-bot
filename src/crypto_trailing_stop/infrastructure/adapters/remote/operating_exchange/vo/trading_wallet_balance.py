from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class TradingWalletBalance:
    currency: str
    balance: float | int
    blocked_balance: float | int = 0.0

    @property
    def is_effective(self) -> bool:
        # XXX: Minimal balance to consider potential losses is 0.01
        return self.balance > 0.01 or self.blocked_balance > 0.01

    @property
    def total_balance(self) -> float | int:
        return self.balance + self.blocked_balance
