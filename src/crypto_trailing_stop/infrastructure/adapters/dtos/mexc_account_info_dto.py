from pydantic import BaseModel, ConfigDict, Field


class MEXCAccountBalanceDto(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    asset: str | None = None
    free: float | int | None = 0.0
    locked: float | int | None = 0.0
    available: float | int | None = 0.0


class MEXCAccountDto(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    maker_commission: float | None = Field(alias="makerCommission", default=None)
    taker_commission: float | None = Field(alias="takerCommission", default=None)
    buyer_commission: float | None = Field(alias="buyerCommission", default=None)
    seller_commission: float | None = Field(alias="sellerCommission", default=None)
    can_trade: bool | None = Field(alias="canTrade", default=False)
    can_withdraw: bool | None = Field(alias="canWithdraw", default=False)
    can_deposit: bool | None = Field(alias="canDeposit", default=False)
    update_time: int | None = Field(alias="updateTime", default=None)
    account_type: str | None = Field(alias="accountType", default=None)
    balances: list[MEXCAccountBalanceDto] | None = Field(alias="balances", default_factory=list)
    permissions: list[str] | None = Field(alias="permissions", default=None)
