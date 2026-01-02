from pydantic import BaseModel, ConfigDict, Field


class MEXCContractAssetDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    currency: str = Field(..., alias="currency")
    position_margin: float = Field(alias="positionMargin", default=0.0)
    available_balance: float = Field(alias="availableBalance", default=0.0)
    cash_balance: float = Field(alias="cashBalance", default=0.0)
    frozen_balance: float = Field(alias="frozenBalance", default=0.0)
    equity: float = Field(alias="equity", default=0.0)
    unrealized: float = Field(alias="unrealized", default=0.0)
    bonus: float = Field(alias="bonus", default=0.0)
    available_cash: float = Field(alias="availableCash", default=0.0)
    available_open: float = Field(alias="availableOpen", default=0.0)
    debt_amount: float = Field(alias="debtAmount", default=0.0)
    contribute_margin_amount: float = Field(alias="contributeMarginAmount", default=0.0)
