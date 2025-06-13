from __future__ import annotations
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic import AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from crypto_trailing_stop.commons.constants import TRAILING_STOP_LOSS_DEFAULT_PERCENT
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

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
    # CORS enabled
    cors_enabled: bool = False
    # Telegram bot token
    telegram_bot_token: str
    # Bit2Me API configuration
    bit2me_api_base_url: AnyUrl
    bit2me_api_key: str
    bit2me_api_secret: str
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
