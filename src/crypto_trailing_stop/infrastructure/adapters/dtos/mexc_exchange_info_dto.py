from pydantic import BaseModel, ConfigDict, Field


class MEXCExchangeSymbolConfigDto(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    symbol: str
    base_asset: str = Field(..., alias="baseAsset")
    base_asset_precision: int = Field(..., alias="baseAssetPrecision")
    quote_asset: str = Field(..., alias="quoteAsset")
    quote_precision: int = Field(..., alias="quotePrecision")
    quote_asset_precision: int | None = Field(alias="quoteAssetPrecision", default=None)
    base_commission_precision: int | None = Field(alias="baseCommissionPrecision", default=None)
    quote_commission_precision: int = Field(alias="quoteCommissionPrecision", default=None)
    is_spot_trading_allowed: bool = Field(alias="isSpotTradingAllowed", default=False)
    is_margin_trading_allowed: bool = Field(alias="isMarginTradingAllowed", default=False)
    quote_amount_precision: str | None = Field(alias="quoteAmountPrecision", default=None)
    maker_commission: str | None = Field(alias="makerCommission", default=None)
    taker_commission: str | None = Field(alias="takerCommission", default=None)
    quote_amount_precision_market: str | None = Field(alias="quoteAmountPrecisionMarket", default=None)
    max_quote_amount_market: str | None = Field(alias="maxQuoteAmountMarket", default=None)
    permissions: list[str] = Field(default_factory=list)


class MEXCExchangeInfoDto(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    symbols: list[MEXCExchangeSymbolConfigDto] = []
