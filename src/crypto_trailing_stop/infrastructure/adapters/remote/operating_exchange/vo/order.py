from dataclasses import dataclass
from datetime import datetime

from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import (
    OrderSideEnum,
    OrderStatusEnum,
    OrderTypeEnum,
)


@dataclass(frozen=True, kw_only=True)
class Order:
    id: str | None = None
    symbol: str
    created_at: datetime
    order_type: OrderTypeEnum
    status: OrderStatusEnum
    side: OrderSideEnum
    amount: float
    price: float | None = None
    stop_price: float | None = None

    @property
    def effective_price(self) -> float | int:
        return self.stop_price if self.stop_price is not None else self.price
