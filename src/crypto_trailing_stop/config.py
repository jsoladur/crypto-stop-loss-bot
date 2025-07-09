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
from pyee.asyncio import AsyncIOEventEmitter

from crypto_trailing_stop.commons.constants import (
    DEFAULT_JOB_INTERVAL_SECONDS,
    DEFAULT_TRAILING_STOP_LOSS_PERCENT,
    STOP_LOSS_STEPS_VALUE_LIST,
)

_configuration_properties: ConfigurationProperties | None = None
_scheduler: AsyncIOScheduler | None = None
_event_emitter: AsyncIOEventEmitter | None = None
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
    # XXX: Better after backtesting in TradingView
    buy_sell_signals_4h_volatility_threshold: float = 0.009
    # XXX: Better after backtesting in TradingView
    buy_sell_signals_1h_volatility_threshold: float = 0.004
    buy_sell_signals_rsi_overbought: int = 70
    buy_sell_signals_rsi_oversold: int = 30
    # Auto-Entry Trader configuration properties
    max_atr_percent_for_auto_entry: int = STOP_LOSS_STEPS_VALUE_LIST[-1]
    # XXX: EMA values
    buy_sell_signals_ema_short_value: int = 7
    buy_sell_signals_ema_mid_value: int = 18
    buy_sell_signals_ema_long_value: int = 200
    # Market Signals parameters
    market_signal_retention_days: int = 9
    # XXX: Other parameters
    suggested_stop_loss_atr_multiplier: float = 1.85
    suggested_take_profit_atr_multiplier: float = 3.0
    # Google OAuth configuration
    google_oauth_client_id: str
    google_oauth_client_secret: str
    # Trailing stop loss configuration
    trailing_stop_loss_percent: float | int = DEFAULT_TRAILING_STOP_LOSS_PERCENT
    # Jobs configuration
    job_interval_seconds: int = DEFAULT_JOB_INTERVAL_SECONDS


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


def get_event_emitter() -> AsyncIOEventEmitter:
    global _event_emitter
    if _event_emitter is None:
        _event_emitter = AsyncIOEventEmitter()
    return _event_emitter


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
