from typing import Optional
from pydantic import BaseModel

class CoinbaseTradingWalletBalanceDto(BaseModel):
    account_id: str
    currency: str
    balance: str
    hold: str
    available: str
    profile_id: str
    trading_enabled: bool
    type: str
    ready: bool
    holds: Optional[dict[str, str]] = None