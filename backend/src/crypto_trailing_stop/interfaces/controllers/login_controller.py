from fastapi import APIRouter

router = APIRouter(prefix="/login", tags=["login"])


@router.get("/oauth")
async def login():
    raise NotImplementedError()
