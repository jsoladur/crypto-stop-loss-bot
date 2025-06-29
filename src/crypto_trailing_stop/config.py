from __future__ import annotations

from uuid import uuid4

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from authlib.integrations.starlette_client import OAuth
from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from crypto_trailing_stop.commons.constants import TRAILING_STOP_LOSS_DEFAULT_PERCENT

_configuration_properties: ConfigurationProperties | None = None
_scheduler: AsyncIOScheduler | None = None
_telegram_bot: Bot | None = None
_dispacher: Dispatcher | None = None


class ConfigurationProperties(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", validate_default=False, extra="allow")
    # Application configuration
    background_tasks_enabled: bool = True
    telegram_bot_enabled: bool = True
    public_domain: str = "http://localhost:8000"
    session_secret_key: str = Field(default_factory=uuid4)
    login_enabled: bool = True
    # CORS enabled
    cors_enabled: bool = False
    # Telegram bot token
    telegram_bot_token: str
    # Database configuration
    database_in_memory: bool = False
    database_path: str = "./crypto_stop_loss.sqlite"
    # Bit2Me API configuration
    bit2me_api_base_url: AnyUrl
    bit2me_api_key: str
    bit2me_api_secret: str
    # Buy Sell Signals configuration
    buy_sell_signals_run_via_cron_pattern: bool = True
    buy_sell_signals_proximity_threshold: float = 0.002
    # XXX: Better after backtesting in TradingView to 0.017
    buy_sell_signals_4h_volatility_threshold: float = 0.017
    # XXX: Better after backtesting in TradingView to 0.005
    buy_sell_signals_1h_volatility_threshold: float = 0.005
    buy_sell_signals_rsi_overbought: int = 70
    buy_sell_signals_rsi_oversold: int = 30
    # Google OAuth configuration
    google_oauth_client_id: str
    google_oauth_client_secret: str
    # Trailing stop loss configuration
    trailing_stop_loss_percent: float | int = TRAILING_STOP_LOSS_DEFAULT_PERCENT
    # Jobs configuration
    job_interval_seconds: int = 10  # 10 seconds


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


def get_telegram_bot() -> Bot:
    global _telegram_bot
    if _telegram_bot is None:
        configuration_properties = get_configuration_properties()
        bot = Bot(
            token=configuration_properties.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
    return bot


def get_dispacher() -> Dispatcher:
    global _dispacher
    if _dispacher is None:
        _dispacher = Dispatcher(storage=MemoryStorage())
    return _dispacher


def get_oauth_context() -> OAuth:  # pragma: no cover
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
