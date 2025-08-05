from dataclasses import dataclass
from datetime import datetime

from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_market_config_dto import Bit2MeMarketConfigDto
from crypto_trailing_stop.infrastructure.tasks.vo.types import MarketSignalType, RSIState, Timeframe


@dataclass
class MarketSignalItem:
    timestamp: datetime
    symbol: str
    timeframe: Timeframe
    signal_type: MarketSignalType
    rsi_state: RSIState
    atr: float
    closing_price: float
    ema_long_price: float

    @property
    def is_buy_sell_signal(self) -> bool:
        return self.signal_type in ["buy", "sell"]

    @property
    def is_divergence_signal(self) -> bool:
        return self.signal_type in ["bearish_divergence", "bullish_divergence"]

    @property
    def is_candidate_to_trigger_buy_action(self) -> bool:
        return self.timeframe == "1h" and self.signal_type == "buy"

    def get_atr_percent(self, trading_market_config: Bit2MeMarketConfigDto) -> float:
        return round((self.atr / self.closing_price) * 100, ndigits=trading_market_config.price_precision)
