from enum import Enum
from typing import Optional
from pydantic import BaseModel

class CoinbaseTradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class CoinbaseTradeDto(BaseModel):
    trade_id: str
    product_id: str
    side: CoinbaseTradeSide
    size: str
    price: str
    fee: str
    total: str
    trade_time: str
    order_id: str
    client_order_id: Optional[str] = None
    trade_type: str
    fee_rate: str
    price_currency: str
    size_currency: str