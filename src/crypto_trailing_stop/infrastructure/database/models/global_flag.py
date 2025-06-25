from piccolo.table import Table
from piccolo.columns import UUID, Text, Boolean
from uuid import UUID as UUIDType, uuid4


class GlobalFlag(Table, tablename="flag"):
    id: UUIDType = UUID(primary_key=True, default=uuid4)
    name: str = Text(unique=True, required=True)
    value: bool = Boolean(required=True)
