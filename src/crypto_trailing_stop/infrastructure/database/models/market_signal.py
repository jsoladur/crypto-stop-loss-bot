from datetime import UTC, datetime
from typing import Literal
from uuid import UUID as UUIDType
from uuid import uuid4

from piccolo.columns import UUID, Text, Timestamp
from piccolo.table import Table


class MarketSignal(Table):
    id: UUIDType = UUID(primary_key=True, default=uuid4)
    timestamp: datetime = Timestamp(required=True, default=lambda: datetime.now(tz=UTC))
    symbol = Text(required=True)
    timeframe: Literal["4h", "1h"] = Text(required=True)
    signal_type: Literal["buy", "sell"] = Text(required=True)
