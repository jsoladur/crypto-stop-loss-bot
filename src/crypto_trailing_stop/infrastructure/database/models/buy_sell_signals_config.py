from uuid import UUID as UUIDType
from uuid import uuid4

from piccolo.columns import UUID, Boolean, Float, Integer, Text
from piccolo.table import Table


class BuySellSignalsConfig(Table):
    id: UUIDType = UUID(primary_key=True, default=uuid4)
    symbol: str = Text(unique=True, required=True)

    # EMA and Risk Parameters
    ema_short_value: int = Integer(required=True)
    ema_mid_value: int = Integer(required=True)
    ema_long_value: int = Integer(required=True)
    stop_loss_atr_multiplier: float = Float(required=True)
    take_profit_atr_multiplier: float = Float(required=True)

    # ADX filter parameters
    enable_adx_filter: bool = Boolean(required=True)
    adx_threshold: int = Integer(required=True)
    # Buy Volume Filter parameters
    enable_buy_volume_filter: bool = Boolean(required=True)
    buy_min_volume_threshold: float = Float(required=True)
    buy_max_volume_threshold: float = Float(required=True)

    # Sell Volume Filter parameters
    enable_sell_volume_filter: bool = Boolean(required=True)
    sell_min_volume_threshold: float = Float(required=True)

    # Exit Parameters
    enable_exit_on_sell_signal: bool = Boolean(required=True)
    enable_exit_on_take_profit: bool = Boolean(required=True)
