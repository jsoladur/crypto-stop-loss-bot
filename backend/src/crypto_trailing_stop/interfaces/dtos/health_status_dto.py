from pydantic import BaseModel


class HealthStatusDto(BaseModel):
    status: bool = True
