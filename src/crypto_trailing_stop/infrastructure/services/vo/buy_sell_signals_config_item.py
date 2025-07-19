from dataclasses import dataclass, field

from crypto_trailing_stop.config import get_configuration_properties


@dataclass
class BuySellSignalsConfigItem:
    symbol: str
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
    auto_exit_sell_1h: bool = True
    auto_exit_atr_take_profit: bool = True

    def __post_init__(self):
        self.symbol = self.symbol.strip().upper()
