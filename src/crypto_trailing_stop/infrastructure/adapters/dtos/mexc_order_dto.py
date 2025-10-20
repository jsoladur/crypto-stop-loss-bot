from abc import ABCMeta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MEXCMeOrderSide = Literal["BUY", "SELL"]
MEXCOrderStatus = Literal["NEW", "FILLED", "PARTIALLY_FILLED", "CANCELED", "PARTIALLY_CANCELED"]
MEXCMeOrderType = Literal["LIMIT", "STOP_LIMIT", "MARKET", "LIMIT_MAKER", "IMMEDIATE_OR_CANCEL", "FILL_OR_KILL"]


class _AbstractMECXOrderDto(BaseModel, metaclass=ABCMeta):
    side: MEXCMeOrderSide
    symbol: str
    type: MEXCMeOrderType


class CreateNewMEXCOrderDto(_AbstractMECXOrderDto):
    quantity: float | int
    price: float | int | None = None
    stop_price: float | int | None = Field(alias="stopPrice", default=None)


class MEXCOrderDto(_AbstractMECXOrderDto):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    order_id: str = Field(..., alias="orderId")
    time: int
    update_time: int | None = Field(alias="updateTime", default=None)
    status: MEXCOrderStatus
    price: str
    qty: str = Field(..., alias="Qty")
    executed_qty: str = Field(..., alias="executedQty")
    cummulative_quote_qty: str = Field(..., alias="cummulativeQuoteQty")
    stop_price: str = Field(..., alias="stopPrice")
    orig_quote_order_qty: str = Field(..., alias="origQuoteOrderQty")
