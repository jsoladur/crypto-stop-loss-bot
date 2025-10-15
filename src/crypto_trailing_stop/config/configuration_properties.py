from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import AnyUrl, Field
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, EnvSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict

from crypto_trailing_stop.commons.constants import (
    DEFAULT_JOB_INTERVAL_SECONDS,
    DEFAULT_TRAILING_STOP_LOSS_PERCENT,
    STOP_LOSS_STEPS_VALUE_LIST,
)


class _CustomEnvSettingsSource(EnvSettingsSource):
    def prepare_field_value(self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool) -> Any:
        if field_name == "authorized_google_user_emails_comma_separated":
            ret = [str(v).strip().lower() for v in value.split(",")] if value else None
        else:
            ret = super().prepare_field_value(field_name, field, value, value_is_complex)
        return ret


class ConfigurationProperties(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", validate_default=False, extra="allow")
    # Application configuration
    background_tasks_enabled: bool = True
    telegram_bot_enabled: bool = True
    public_domain: str = "http://localhost:8000"
    session_secret_key: str = Field(default_factory=lambda: str(uuid4()))
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
    # XXX: ADX threshold
    buy_sell_signals_adx_threshold: int = 15
    # XXX: Min/Max Relative Volume threshold
    buy_sell_signals_min_volume_threshold: float = 0.45
    buy_sell_signals_max_volume_threshold: float = 3.5
    # Auto-Entry Trader configuration properties
    max_atr_percent_for_auto_entry: int = STOP_LOSS_STEPS_VALUE_LIST[-1]
    # XXX: EMA values (after backtesting EMA 9/21 is the best for mostly all crypto currencies)
    buy_sell_signals_ema_short_value: int = 9
    buy_sell_signals_ema_mid_value: int = 21
    buy_sell_signals_ema_long_value: int = 200
    # Trailing stop loss configuration
    trailing_stop_loss_percent: float | int = DEFAULT_TRAILING_STOP_LOSS_PERCENT
    # Market Signals parameters
    market_signal_retention_days: int = 9
    # XXX: ATR multipliers (RRR = 1.4)
    suggested_stop_loss_atr_multiplier: float = 2.5
    suggested_take_profit_atr_multiplier: float = 3.5
    # Google OAuth configuration
    authorized_google_user_emails_comma_separated: list[str]
    google_oauth_client_id: str
    google_oauth_client_secret: str
    # Gemini Pro configuration
    gemini_pro_api_enabled: bool = False
    gemini_pro_api_key: str | None = None
    # Jobs configuration
    job_interval_seconds: int = DEFAULT_JOB_INTERVAL_SECONDS

    @classmethod
    def settings_customise_sources(
        cls, settings_cls: type[BaseSettings], *_, **__
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (_CustomEnvSettingsSource(settings_cls),)
