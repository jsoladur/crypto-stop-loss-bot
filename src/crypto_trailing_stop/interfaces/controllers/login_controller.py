import logging
from typing import Annotated
from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter, Query, Request, Response, status

from crypto_trailing_stop.config.dependencies import get_application_container, get_oauth_context
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.dtos.login_dto import LoginDto
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.interfaces.telegram.services import TelegramService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/login", tags=["login"])

application_container = get_application_container()
configuration_properties = application_container.configuration_properties()
keyboards_builder: KeyboardsBuilder = (
    application_container.interfaces_container().telegram_container().keyboards_builder()
)
session_storage_service: SessionStorageService = (
    application_container.infrastructure_container().services_container().session_storage_service()
)
telegram_service: TelegramService = application_container.interfaces_container().telegram_container().telegram_service()


@router.get("/oauth")
async def login(login_query_params: Annotated[LoginDto, Query()], request: Request) -> Response:
    if not configuration_properties.telegram_bot_enabled:
        response = Response(status_code=status.HTTP_412_PRECONDITION_FAILED)
    elif "userinfo" in request.session:
        userinfo = request.session["userinfo"]
        await telegram_service.perform_successful_login(login=login_query_params, userinfo=userinfo)
        response = Response(status_code=status.HTTP_200_OK)
    else:
        request.session["login_query_params"] = login_query_params.model_dump(mode="python")
        parsed_public_domain = urlparse(configuration_properties.public_domain)
        parsed_login_callback_url = request.url_for("login_callback")
        redirect_uri = urlunparse(
            (
                parsed_public_domain.scheme,
                parsed_public_domain.netloc,
                parsed_login_callback_url.path,
                "",
                parsed_login_callback_url.query,
                parsed_login_callback_url.fragment,
            )
        )
        logger.info(f"Redirecting to Google OAuth with redirect URI: {redirect_uri}")
        oauth_context = get_oauth_context()
        google_auth = oauth_context.create_client("google")
        response = await google_auth.authorize_redirect(request, redirect_uri)
    return response


@router.get("/oauth/callback")
async def login_callback(request: Request) -> Response:
    if not configuration_properties.telegram_bot_enabled:
        response = Response(status_code=status.HTTP_412_PRECONDITION_FAILED)
    elif "login_query_params" not in request.session:
        logger.warning("Login query parameters not found in session.")
        response = Response(
            status_code=status.HTTP_400_BAD_REQUEST, content="Login query parameters not found in session."
        )
    else:
        login_query_params = LoginDto.model_validate(request.session["login_query_params"])
        oauth_context = get_oauth_context()
        google_auth = oauth_context.create_client("google")
        token = await google_auth.authorize_access_token(request)
        userinfo = request.session["userinfo"] = token["userinfo"]
        if userinfo["email"] not in configuration_properties.authorized_google_user_emails_comma_separated:
            logger.warning(f"Unauthorized user: {userinfo['email']}")
            await telegram_service.send_message(
                chat_id=login_query_params.tg_chat_id, text="Unauthorized user. Please contact the administrator."
            )
            response = Response(status_code=status.HTTP_403_FORBIDDEN, content="Unauthorized user")
        else:
            logger.info(f"User authenticated successfully: {userinfo['email']}")
            await telegram_service.perform_successful_login(login=login_query_params, userinfo=userinfo)
            response = Response(status_code=status.HTTP_200_OK, content="Login successful. You can close this window.")
    return response
