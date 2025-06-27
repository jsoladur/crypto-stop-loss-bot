from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class Profile(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    currency_code: str = Field(alias="currencyCode", default=...)


class Bit2MeAccountInfoDto(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    profile: Profile
    registration_date: datetime = Field(alias="registrationDate", default=...)
