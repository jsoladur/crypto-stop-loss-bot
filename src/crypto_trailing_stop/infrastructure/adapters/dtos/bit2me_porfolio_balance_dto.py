from pydantic import BaseModel, ConfigDict, Field


class ConvertedBalanceDto(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    currency: str
    value: float | int


class WalletDto(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    balance: float | int
    currency: str
    converted_balance: ConvertedBalanceDto | None = Field(alias="convertedBalance", default=None)


class TotalDto(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    converted_balance: ConvertedBalanceDto = Field(alias="convertedBalance", default=...)


class Bit2MePortfolioBalanceDto(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    service_name: str = Field(alias="serviceName", default=...)
    total: TotalDto
    wallets: list[WalletDto] = Field(default_factory=list)
