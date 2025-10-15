from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class BuySellSignalsConfigItem:
    symbol: str
    # EMA and Risk Parameters
    ema_short_value: int
    ema_mid_value: int
    ema_long_value: int
    stop_loss_atr_multiplier: float
    take_profit_atr_multiplier: float
    # ADX filter parameters
    enable_adx_filter: bool = True
    adx_threshold: int
    # Buy Volume Filter parameters
    enable_buy_volume_filter: bool = True
    buy_min_volume_threshold: float
    buy_max_volume_threshold: float
    # Sell Volume Filter parameters
    enable_sell_volume_filter: bool = False
    sell_min_volume_threshold: float
    # Exit Parameters
    enable_exit_on_sell_signal: bool = True
    enable_exit_on_take_profit: bool = False

    def __post_init__(self):
        self.symbol = self.symbol.strip().upper()
