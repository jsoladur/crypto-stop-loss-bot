from pydantic import BaseModel, ConfigDict, Field


class MEXCTradeDto(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    id: str
    time: int
    symbol: str
    order_id: str = Field(..., alias="orderId")
    price: float | int
    qty: float | int
    quote_qty: float | int = Field(..., alias="quoteQty")
    commission: float | int
    commission_asset: float | int = Field(..., alias="commissionAsset")
    is_buyer: bool = Field(..., alias="isBuyer")
    is_maker: bool = Field(..., alias="isMaker")
    is_best_match: bool = Field(..., alias="isBestMatch")
    is_self_trade: bool = Field(..., alias="isSelfTrade")
