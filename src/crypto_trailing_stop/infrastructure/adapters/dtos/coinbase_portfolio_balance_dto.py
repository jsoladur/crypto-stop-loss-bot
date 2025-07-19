from typing import Optional
from pydantic import BaseModel

class CoinbasePortfolioBalanceDto(BaseModel):
    currency: str
    balance: str
    available: str
    hold: str
    profile_id: str
    trading_enabled: bool
    convertible_to: list[str]
    price: Optional[str] = None
    price_percentage_change_24h: Optional[str] = None
    value: Optional[str] = None