from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram_dialog import setup_dialogs
from authlib.integrations.starlette_client import OAuth

from crypto_trailing_stop.config.application_container import ApplicationContainer
from crypto_trailing_stop.config.configuration_properties import ConfigurationProperties

_application_container: ApplicationContainer | None = None
_telegram_bot: Bot | None = None
_dispacher: Dispatcher | None = None


def get_application_container() -> ApplicationContainer:
    global _application_container
    if _application_container is None:
        _application_container = ApplicationContainer()
        _application_container.check_dependencies()
    return _application_container


def get_telegram_bot(configuration_properties: ConfigurationProperties) -> Bot:
    global _telegram_bot
    if _telegram_bot is None:
        bot = Bot(
            token=configuration_properties.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
    return bot


def get_dispacher() -> Dispatcher:
    global _dispacher
    if _dispacher is None:
        _dispacher = Dispatcher(storage=MemoryStorage())
        setup_dialogs(_dispacher)
    return _dispacher


def get_oauth_context(configuration_properties: ConfigurationProperties) -> OAuth:  # pragma: no cover
    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=configuration_properties.google_oauth_client_id,
        client_secret=configuration_properties.google_oauth_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    return oauth
