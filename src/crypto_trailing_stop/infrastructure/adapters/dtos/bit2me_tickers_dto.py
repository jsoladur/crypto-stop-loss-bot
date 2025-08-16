from pydantic import BaseModel, Field


class Bit2MeTickersDto(BaseModel):
    timestamp: int
    symbol: str
    close: float | int
    bid: float | int
    ask: float | int
    open: float | int | None = None
    high: float | int | None = None
    low: float | int | None = None
    percentage: float | int | None = None
    base_volume: float | int | None = Field(None, alias="baseVolume")
    quote_volume: float | int | None = Field(None, alias="quoteVolume")
