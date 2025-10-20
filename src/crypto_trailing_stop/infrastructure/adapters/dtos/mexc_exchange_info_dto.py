from pydantic import BaseModel, ConfigDict, Field


class MEXCExchangeSymbolConfigDto(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    symbol: str
    base_asset: str = Field(alias="baseAsset")
    base_asset_precision: int = Field(alias="baseAssetPrecision")
    quote_asset: str = Field(alias="quoteAsset")
    quote_precision: int = Field(alias="quotePrecision")
    quote_asset_precision: int = Field(alias="quoteAssetPrecision")
    base_commission_precision: int = Field(alias="baseCommissionPrecision")
    quote_commission_precision: int = Field(alias="quoteCommissionPrecision")
    is_spot_trading_allowed: bool = Field(alias="isSpotTradingAllowed")
    is_margin_trading_allowed: bool = Field(alias="isMarginTradingAllowed")
    quote_amount_precision: str = Field(alias="quoteAmountPrecision")
    base_size_precision: str = Field(alias="baseSizePrecision")
    maker_commission: str = Field(alias="makerCommission")
    taker_commission: str = Field(alias="takerCommission")
    quote_amount_precision_market: str = Field(alias="quoteAmountPrecisionMarket")
    max_quote_amount_market: str = Field(alias="maxQuoteAmountMarket")
    permissions: list[str] = []


class MEXCExchangeInfoDto(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    symbols: list[MEXCExchangeSymbolConfigDto] = []
