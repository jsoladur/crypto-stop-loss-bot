from typing import Optional
from pydantic import BaseModel

class CoinbaseTickersDto(BaseModel):
    product_id: str
    price: str
    volume_24h: str
    volume_30d: str
    volume_30d_quote: str
    volume_24h_quote: str
    price_percentage_change_24h: str
    number_of_trades_24h: str
    low_24h: str
    high_24h: str
    open_24h: str
    volume_percentage_change_24h: str
    last_trade_price: Optional[str] = None
    best_bid: Optional[str] = None
    best_ask: Optional[str] = None