from dataclasses import dataclass


@dataclass
class AutoBuyTraderConfigItem:
    symbol: str
    fiat_wallet_percent_assigned: int = 0

    def __post_init__(self):
        self.symbol = self.symbol.strip().upper()
        if self.fiat_wallet_percent_assigned < 0 or self.fiat_wallet_percent_assigned > 100:  # pragma: no cover
            raise ValueError("'fiat_wallet_percent_assigned' must be a percent value (%) between 0 and 100")
