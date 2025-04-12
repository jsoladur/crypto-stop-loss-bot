from fastapi import APIRouter
from crypto_trailing_stop.interfaces.dtos.health_status import HealthStatus

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/status")
async def health_check():
    return HealthStatus()
