from uuid import UUID as UUIDType
from uuid import uuid4

from piccolo.columns import UUID, Text
from piccolo.table import Table


class FavouriteCryptoCurrency(Table):
    id: UUIDType = UUID(primary_key=True, default=uuid4)
    currency: str = Text(unique=True, required=True)
