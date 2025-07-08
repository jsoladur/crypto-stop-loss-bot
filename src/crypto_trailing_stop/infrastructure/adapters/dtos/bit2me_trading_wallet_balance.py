from pydantic import BaseModel, ConfigDict, Field


class Bit2MeTradingWalletBalanceDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True, extra="ignore")

    id: str
    currency: str
    balance: float | int
    blocked_balance: float | int = Field(alias="blockedBalance", default=0.0)
