from uuid import UUID as UUIDType
from uuid import uuid4

from piccolo.columns import UUID, Boolean, Text
from piccolo.table import Table


class GlobalFlag(Table, tablename="flag"):
    id: UUIDType = UUID(primary_key=True, default=uuid4)
    name: str = Text(unique=True, required=True)
    value: bool = Boolean(required=True)
