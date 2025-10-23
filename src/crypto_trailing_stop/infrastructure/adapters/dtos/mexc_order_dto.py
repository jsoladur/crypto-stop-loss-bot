from abc import ABCMeta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MEXCOrderSide = Literal["BUY", "SELL"]
MEXCOrderStatus = Literal["NEW", "FILLED", "PARTIALLY_FILLED", "CANCELED", "PARTIALLY_CANCELED"]
MEXCOrderType = Literal["LIMIT", "STOP_LIMIT", "MARKET", "LIMIT_MAKER", "IMMEDIATE_OR_CANCEL", "FILL_OR_KILL"]


class _AbstractMECXOrderDto(BaseModel, metaclass=ABCMeta):
    side: MEXCOrderSide
    symbol: str
    type: MEXCOrderType


class CreateNewMEXCOrderDto(_AbstractMECXOrderDto):
    quantity: float | int
    price: float | int | None = None
    stop_price: float | int | None = Field(alias="stopPrice", default=None)


class MEXCOrderCreatedDto(_AbstractMECXOrderDto):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    order_id: str | int = Field(..., alias="orderId")
    price: str
    orig_qty: str = Field(..., alias="origQty")


class MEXCOrderDto(_AbstractMECXOrderDto):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    order_id: str | int = Field(..., alias="orderId")
    time: int
    update_time: int | None = Field(alias="updateTime", default=None)
    status: MEXCOrderStatus
    price: str
    orig_qty: str = Field(..., alias="origQty")
    executed_qty: str | None = Field(alias="executedQty", default=None)
    stop_price: str | None = Field(alias="stopPrice", default=None)
