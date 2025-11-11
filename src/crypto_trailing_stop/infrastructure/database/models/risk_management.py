from uuid import UUID as UUIDType
from uuid import uuid4

from piccolo.columns import UUID, Float
from piccolo.table import Table


class RiskManagement(Table, tablename="flag"):
    id: UUIDType = UUID(primary_key=True, default=uuid4)
    value: float = Float(required=True)
