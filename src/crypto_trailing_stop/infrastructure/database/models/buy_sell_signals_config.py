from uuid import UUID as UUIDType
from uuid import uuid4

from piccolo.columns import UUID, Boolean, Integer, Text
from piccolo.table import Table


class BuySellSignalsConfig(Table):
    id: UUIDType = UUID(primary_key=True, default=uuid4)
    symbol: str = Text(unique=True, required=True)
    ema_short_value: int = Integer(required=True)
    ema_mid_value: int = Integer(required=True)
    ema_long_value: int = Integer(required=True)
    auto_exit_sell_1h: bool = Boolean(required=True)
    auto_exit_atr_take_profit: bool = Boolean(required=True)
