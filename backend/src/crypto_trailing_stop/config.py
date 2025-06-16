from __future__ import annotations
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic import AnyUrl
from uuid import uuid4
from pydantic_settings import BaseSettings, SettingsConfigDict
from crypto_trailing_stop.commons.constants import TRAILING_STOP_LOSS_DEFAULT_PERCENT
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from authlib.integrations.starlette_client import OAuth
from pydantic import Field


_configuration_properties: ConfigurationProperties | None = None
_scheduler: AsyncIOScheduler | None = None
_dispacher: Dispatcher | None = None


class ConfigurationProperties(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        validate_default=False,
        extra="allow",
    )
    # Application configuration
    background_tasks_enabled: bool = True
    public_domain: str = "http://localhost:8000"
    session_secret_key: str = Field(default_factory=uuid4)
    # CORS enabled
    cors_enabled: bool = False
    # Telegram bot token
    telegram_bot_token: str
    # Bit2Me API configuration
    bit2me_api_base_url: AnyUrl
    bit2me_api_key: str
    bit2me_api_secret: str
    # Google OAuth configuration
    google_oauth_client_id: str
    google_oauth_client_secret: str
    # Trailing stop loss configuration
    trailing_stop_loss_percent: float | int = TRAILING_STOP_LOSS_DEFAULT_PERCENT
    # Jobs configuration
    job_interval_seconds: int = 10


def get_configuration_properties() -> ConfigurationProperties:
    global _configuration_properties
    if _configuration_properties is None:
        _configuration_properties = ConfigurationProperties()
    return _configuration_properties


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def get_dispacher() -> Dispatcher:
    global _dispacher
    if _dispacher is None:
        _dispacher = Dispatcher(storage=MemoryStorage())
    return _dispacher


def get_oauth_context() -> OAuth:
    configuration_properties = get_configuration_properties()
    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=configuration_properties.google_oauth_client_id,
        client_secret=configuration_properties.google_oauth_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    return oauth
