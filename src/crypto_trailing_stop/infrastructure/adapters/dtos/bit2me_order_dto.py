from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from abc import ABCMeta

Bit2MeOrderStatus = Literal["open", "filled", "cancelled", "inactive"]
Bit2MeOrderSide = Literal["buy", "sell"]
Bit2MeOrderType = Literal["stop-limit", "limit", "market"]


class _AbstractBit2MeOrderDto(BaseModel, metaclass=ABCMeta):
    side: Bit2MeOrderSide
    symbol: str
    order_type: Bit2MeOrderType = Field(..., alias="orderType")


class CreateNewBit2MeOrderDto(_AbstractBit2MeOrderDto):
    model_config = ConfigDict(
        populate_by_name=True, use_enum_values=True, extra="ignore"
    )

    amount: str
    price: str | None = None
    stop_price: str | None = Field(None, alias="stopPrice")


class Bit2MeOrderDto(_AbstractBit2MeOrderDto):
    model_config = ConfigDict(
        populate_by_name=True, use_enum_values=True, extra="ignore"
    )
    id: str
    status: Bit2MeOrderStatus
    order_amount: float | int = Field(..., alias="orderAmount")
    stop_price: float | int | None = Field(None, alias="stopPrice")
    price: float | int

    @property
    def effective_price(self) -> float | int:
        return self.stop_price if self.stop_price is not None else self.price


CreateNewBit2MeOrderDto.model_rebuild()
Bit2MeOrderDto.model_rebuild()

__all__ = ["CreateNewBit2MeOrderDto", "Bit2MeOrderDto"]
