from fastapi import APIRouter

from crypto_trailing_stop.interfaces.dtos.health_status_dto import HealthStatusDto

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/status")
async def health_check():
    return HealthStatusDto()
