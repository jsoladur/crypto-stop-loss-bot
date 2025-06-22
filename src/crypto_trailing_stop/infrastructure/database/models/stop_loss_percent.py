from piccolo.table import Table
from piccolo.columns import UUID, Text, Float
from uuid import UUID as UUIDType, uuid4


class StopLossPercent(Table):
    id: UUIDType = UUID(primary_key=True, default=uuid4)
    symbol: str = Text(unique=True, required=True)
    value: float = Float(required=True)
