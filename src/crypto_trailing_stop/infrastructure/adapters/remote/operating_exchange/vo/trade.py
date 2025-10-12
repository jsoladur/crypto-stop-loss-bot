from dataclasses import dataclass

from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import OrderSideEnum


@dataclass(frozen=True, kw_only=True)
class Trade:
    id: str
    symbol: str
    side: OrderSideEnum
    order_id: str | None = None
    price: float | int
    amount: float | int
    fee_amount: float | int

    @property
    def amount_after_fee(self) -> float:
        return self.amount - self.fee_amount
