import logging
from fastapi import Request, APIRouter, Query, JSONResponse, Response, status
from typing import Annotated
from crypto_trailing_stop.interfaces.dtos.login_dto import LoginDto
from crypto_trailing_stop.config import get_oauth_context
from crypto_trailing_stop.commons.constants import AUTHORIZED_GOOGLE_USER_EMAILS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/login", tags=["login"])


@router.get("/oauth")
async def login(
    login_query_params: Annotated[LoginDto, Query()], request: Request
) -> Response:
    if "userinfo" in request.session:
        response = Response(status_code=status.HTTP_200_OK)

    else:
        request.session["login_query_params"] = login_query_params.model_dump(
            mode="python"
        )
        redirect_uri = request.url_for("login_callback")
        oauth_context = get_oauth_context()
        google_auth = oauth_context.create_client("google")
        response = await google_auth.authorize_redirect(request, redirect_uri)
    return response


@router.get("/oauth/callback")
async def login_callback(request: Request) -> Response:
    oauth_context = get_oauth_context()
    google_auth = oauth_context.create_client("google")
    token = await google_auth.authorize_access_token(request)
    if token["email"] not in AUTHORIZED_GOOGLE_USER_EMAILS:
        logger.warning(f"Unauthorized user: {token['email']}")
        response = JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"details": "Unauthorized user"},
        )
    else:
        logger.info(f"User authenticated successfully: {token['email']}")
        request.session["userinfo"] = token["userinfo"]
    return response
