from uuid import UUID as UUIDType
from uuid import uuid4

from piccolo.columns import UUID, Float, Text
from piccolo.table import Table


class StopLossPercent(Table):
    id: UUIDType = UUID(primary_key=True, default=uuid4)
    symbol: str = Text(unique=True, required=True)
    value: float = Float(required=True)
