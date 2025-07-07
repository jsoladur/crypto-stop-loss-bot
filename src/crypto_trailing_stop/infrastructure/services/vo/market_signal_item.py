from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderSide
from crypto_trailing_stop.infrastructure.tasks.vo.types import Timeframe


@dataclass
class MarketSignalItem:
    timestamp: datetime
    symbol: str
    timeframe: Timeframe
    signal_type: Bit2MeOrderSide
    rsi_state: Literal["neutral", "overbought", "oversold"]
    atr: float
    closing_price: float
    ema_long_price: float
