from dataclasses import dataclass, field

from crypto_trailing_stop.config import get_configuration_properties


@dataclass
class BuySellSignalsConfigItem:
    symbol: str
    # EMA and Risk Parameters
    ema_short_value: int = field(
        default_factory=lambda: get_configuration_properties().buy_sell_signals_ema_short_value
    )
    ema_mid_value: int = field(default_factory=lambda: get_configuration_properties().buy_sell_signals_ema_mid_value)
    ema_long_value: int = field(default_factory=lambda: get_configuration_properties().buy_sell_signals_ema_long_value)
    stop_loss_atr_multiplier: float = field(
        default_factory=lambda: get_configuration_properties().suggested_stop_loss_atr_multiplier
    )
    take_profit_atr_multiplier: float = field(
        default_factory=lambda: get_configuration_properties().suggested_take_profit_atr_multiplier
    )

    # ADX filter parameters
    enable_adx_filter: bool = True
    adx_threshold: int = field(default_factory=lambda: get_configuration_properties().buy_sell_signals_adx_threshold)

    # Buy Volume Filter parameters
    enable_buy_volume_filter: bool = True
    buy_min_volume_threshold: float = field(
        default_factory=lambda: get_configuration_properties().buy_sell_signals_min_volume_threshold
    )
    buy_max_volume_threshold: float = field(
        default_factory=lambda: get_configuration_properties().buy_sell_signals_max_volume_threshold
    )

    # Sell Volume Filter parameters
    enable_sell_volume_filter: bool = False
    sell_min_volume_threshold: float = field(
        default_factory=lambda: get_configuration_properties().buy_sell_signals_min_volume_threshold
    )

    # Exit Parameters
    enable_exit_on_sell_signal: bool = True
    enable_exit_on_take_profit: bool = False

    def __post_init__(self):
        self.symbol = self.symbol.strip().upper()
