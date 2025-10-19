from pydantic import BaseModel, ConfigDict, Field


class MEXCTickerBookDto(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    symbol: str
    bid_price: float | int | None = Field(alias="bidPrice", default=None)
    ask_price: float | int | None = Field(alias="askPrice", default=None)
