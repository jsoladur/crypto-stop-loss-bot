from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Bit2MeTradeSide = Literal["buy", "sell"]


class Bit2MeTradeDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True, extra="ignore")

    id: str
    order_id: str = Field(..., alias="orderId")
    symbol: str
    side: Bit2MeTradeSide
    price: float | int
    amount: float | int


Bit2MeTradeDto.model_rebuild()
