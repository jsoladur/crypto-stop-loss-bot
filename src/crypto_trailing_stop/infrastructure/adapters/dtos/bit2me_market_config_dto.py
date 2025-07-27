from pydantic import BaseModel, ConfigDict, Field


class Bit2MeMarketConfigDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True, extra="ignore")

    id: str
    symbol: str
    min_amount: float | int = Field(..., alias="minAmount")
    max_amount: float | int = Field(..., alias="maxAmount")
    min_price: float = Field(..., alias="minPrice")
    max_price: float = Field(..., alias="maxPrice")
    price_precision: int = Field(..., alias="pricePrecision")
    amount_precision: int = Field(..., alias="amountPrecision")
