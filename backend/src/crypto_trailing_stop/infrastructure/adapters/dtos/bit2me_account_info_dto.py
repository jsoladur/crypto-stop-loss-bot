from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class Bit2MeAccountInfoDto(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    registration_date: datetime = Field(alias="registrationDate", default=...)
