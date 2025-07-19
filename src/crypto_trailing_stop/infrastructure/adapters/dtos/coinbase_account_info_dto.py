from typing import Optional
from pydantic import BaseModel

class CoinbaseAccountInfoDto(BaseModel):
    id: str
    name: str
    primary: bool
    type: str
    currency: str
    balance: str
    available: str
    hold: str
    profile_id: str
    trading_enabled: bool