from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class PortfolioBalance:
    spot_balance: float = 0.0
    futures_balance: float = 0.0

    @property
    def total_balance(self) -> float:
        return round(self.spot_balance + self.futures_balance, ndigits=2)
