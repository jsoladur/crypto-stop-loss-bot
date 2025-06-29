from dataclasses import dataclass

from crypto_trailing_stop.infrastructure.services.enums import PushNotificationTypeEnum


@dataclass
class PushNotificationItem:
    telegram_chat_id: int
    notification_type: PushNotificationTypeEnum
    activated: bool
