from uuid import UUID as UUIDType
from uuid import uuid4

from piccolo.columns import UUID, Boolean, Integer, Text
from piccolo.table import Table

from crypto_trailing_stop.config import get_configuration_properties


class BuySellSignalsConfig(Table):
    id: UUIDType = UUID(primary_key=True, default=uuid4)
    symbol: str = Text(unique=True, required=True)
    ema_short_value: int = Integer(
        required=True, default=lambda: get_configuration_properties().buy_sell_signals_ema_short_value
    )
    ema_mid_value: int = Integer(
        required=True, default=lambda: get_configuration_properties().buy_sell_signals_ema_mid_value
    )
    ema_long_value: int = Integer(
        required=True, default=lambda: get_configuration_properties().buy_sell_signals_ema_long_value
    )
    auto_exit_sell_1h: bool = Boolean(required=True, default=True)
    auto_exit_atr_take_profit: bool = Boolean(required=True, default=True)
