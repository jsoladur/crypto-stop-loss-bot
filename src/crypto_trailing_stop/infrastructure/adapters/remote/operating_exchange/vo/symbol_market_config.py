from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class SymbolMarketConfig:
    symbol: str
    price_precision: int
    amount_precision: int
