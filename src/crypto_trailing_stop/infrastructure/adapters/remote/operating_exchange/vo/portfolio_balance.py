from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class PortfolioBalance:
    total_balance: float | int
