from datetime import UTC, datetime
from uuid import UUID as UUIDType
from uuid import uuid4

from piccolo.columns import UUID, Float, Text, Timestamp
from piccolo.table import Table

from crypto_trailing_stop.infrastructure.tasks.vo.types import MarketSignalType, RSIState, Timeframe


class MarketSignal(Table):
    id: UUIDType = UUID(primary_key=True, default=uuid4)
    timestamp: datetime = Timestamp(required=True, default=lambda: datetime.now(tz=UTC))
    symbol = Text(required=True)
    timeframe: Timeframe = Text(required=True)
    signal_type: MarketSignalType = Text(required=True)
    rsi_state: RSIState = Text(required=True)
    atr: float = Float(required=True)
    closing_price: float = Float(required=True)
    ema_long_price: float = Float(required=True)
