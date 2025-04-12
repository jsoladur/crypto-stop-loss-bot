from pydantic import BaseModel, ConfigDict
from typing import Literal


class Bit2MeOrderDto(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True, use_enum_values=True, extra="ignore"
    )
    id: str
    side: Literal["buy", "sell"]
    status: Literal["open", "filled", "cancelled", "inactive"]
    symbol: str
    price: float | int
