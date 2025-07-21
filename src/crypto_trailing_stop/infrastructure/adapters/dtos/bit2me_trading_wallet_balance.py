from pydantic import BaseModel, ConfigDict, Field


class Bit2MeTradingWalletBalanceDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True, extra="ignore")

    id: str
    currency: str
    balance: float | int
    blocked_balance: float | int = Field(alias="blockedBalance", default=0.0)

    @property
    def is_effective(self) -> bool:
        # XXX: Minimal balance to consider potential losses is 0.1
        return self.balance > 0.1 or self.blocked_balance > 0.1

    @property
    def total_balance(self) -> float | int:
        return self.balance + self.blocked_balance
