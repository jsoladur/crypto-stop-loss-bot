from pydantic import BaseModel, ConfigDict


class MEXCTickerPriceDto(BaseModel):
    model_config = ConfigDict(extra="ignore")
    symbol: str
    price: float | int
