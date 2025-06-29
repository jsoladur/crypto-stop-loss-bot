from uuid import UUID as UUIDType
from uuid import uuid4

from piccolo.columns import UUID, Boolean, Integer, Text
from piccolo.table import Table


class PushNotification(Table):
    id: UUIDType = UUID(primary_key=True, default=uuid4)
    telegram_chat_id: int = Integer(required=True)
    notification_type: str = Text(required=True)
    activated: bool = Boolean(required=True, default=True)
