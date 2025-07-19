from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class CoinbaseOrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class CoinbaseOrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"

class CoinbaseOrderStatus(str, Enum):
    OPEN = "OPEN"
    PENDING = "PENDING"
    REJECTED = "REJECTED"
    DONE = "DONE"
    CANCELLED = "CANCELLED"

class CreateNewCoinbaseOrderDto(BaseModel):
    client_order_id: Optional[str] = None
    product_id: str
    side: CoinbaseOrderSide
    order_type: CoinbaseOrderType = Field(alias="type")
    amount: Optional[str] = None
    price: Optional[str] = None
    stop_price: Optional[str] = None
    size: Optional[str] = None
    time_in_force: Optional[str] = None

class CoinbaseOrderDto(BaseModel):
    id: str
    client_order_id: Optional[str] = None
    product_id: str
    user_id: str
    order_type: CoinbaseOrderType = Field(alias="type")
    side: CoinbaseOrderSide
    status: CoinbaseOrderStatus
    time_in_force: str
    created_time: str
    completion_percentage: str
    filled_size: str
    average_filled_price: str
    fee: str
    number_of_fills: str
    filled_value: str
    pending_cancel: bool
    size: Optional[str] = None
    price: Optional[str] = None
    total_fees: Optional[str] = None
    size_in_quote: bool
    total_value_after_fees: Optional[str] = None
    trigger_status: Optional[str] = None
    order_placement_source: Optional[str] = None