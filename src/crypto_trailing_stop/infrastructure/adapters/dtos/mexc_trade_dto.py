from pydantic import BaseModel, ConfigDict, Field


class MEXCTradeDto(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    id: str
    time: int
    symbol: str
    price: float | int
    qty: float | int
    commission: float | int
    is_buyer: bool = Field(..., alias="isBuyer")
    order_id: str | None = Field(alias="orderId", default=None)
    quote_qty: float | int | None = Field(alias="quoteQty", default=None)
    commission_asset: float | int | None = Field(alias="commissionAsset", default=None)
