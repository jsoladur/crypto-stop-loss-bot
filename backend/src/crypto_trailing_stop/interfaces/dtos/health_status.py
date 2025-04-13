from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: bool = True
