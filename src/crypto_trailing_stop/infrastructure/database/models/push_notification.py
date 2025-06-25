from piccolo.table import Table
from piccolo.columns import UUID, Text, Boolean, Integer
from uuid import UUID as UUIDType, uuid4


class PushNotification(Table):
    id: UUIDType = UUID(primary_key=True, default=uuid4)
    telegram_chat_id: int = Integer(required=True)
    notification_type: str = Text(required=True)
    activated: bool = Boolean(required=True, default=True)
