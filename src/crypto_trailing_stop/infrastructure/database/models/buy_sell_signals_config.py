from uuid import UUID as UUIDType
from uuid import uuid4

from piccolo.columns import UUID, Boolean, Float, Integer, Text
from piccolo.table import Table


class BuySellSignalsConfig(Table):
    id: UUIDType = UUID(primary_key=True, default=uuid4)
    symbol: str = Text(unique=True, required=True)
    ema_short_value: int = Integer(required=True)
    ema_mid_value: int = Integer(required=True)
    ema_long_value: int = Integer(required=True)
    stop_loss_atr_multiplier: float = Float(required=True)
    take_profit_atr_multiplier: float = Float(required=True)
    filter_noise_using_adx: bool = Boolean(required=True)
    adx_threshold: int = Integer(required=True)
    apply_volume_filter: bool = Boolean(required=True)
    min_volume_threshold: float = Float(required=True)
    max_volume_threshold: float = Float(required=True)
    auto_exit_sell_1h: bool = Boolean(required=True)
    auto_exit_atr_take_profit: bool = Boolean(required=True)
