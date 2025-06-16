from fastapi import APIRouter, Query, Response
from crypto_trailing_stop.interfaces.dtos.login_dto import LoginDto

router = APIRouter(prefix="/login", tags=["login"])


@router.get("/oauth")
async def login(login_query_params: LoginDto = Query()) -> Response:
    raise NotImplementedError()
