from dataclasses import dataclass
from datetime import datetime

from crypto_trailing_stop.commons.constants import (
    DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE,
    NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL,
)
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_order_dto import Bit2MeOrderSide
from crypto_trailing_stop.infrastructure.tasks.vo.types import RSIState, Timeframe


@dataclass
class MarketSignalItem:
    timestamp: datetime
    symbol: str
    timeframe: Timeframe
    signal_type: Bit2MeOrderSide
    rsi_state: RSIState
    atr: float
    closing_price: float
    ema_long_price: float

    @property
    def is_candidate_to_trigger_buy_action(self) -> bool:
        return self.timeframe == "1h" and self.signal_type == "buy"

    @property
    def atr_percent(self) -> float:
        return round(
            (self.atr / self.closing_price) * 100,
            ndigits=NUMBER_OF_DECIMALS_IN_PRICE_BY_SYMBOL.get(self.symbol, DEFAULT_NUMBER_OF_DECIMALS_IN_PRICE),
        )
