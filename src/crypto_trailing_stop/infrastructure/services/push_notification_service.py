import logging

from crypto_trailing_stop.config.configuration_properties import ConfigurationProperties
from crypto_trailing_stop.infrastructure.database.models.push_notification import PushNotification
from crypto_trailing_stop.infrastructure.services.enums import PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.vo.push_notification_item import PushNotificationItem

logger = logging.getLogger(__name__)


class PushNotificationService:
    def __init__(self, configuration_properties: ConfigurationProperties) -> None:
        self._configuration_properties = configuration_properties

    async def find_push_notification_by_telegram_chat_id(self, telegram_chat_id: int) -> list[PushNotificationItem]:
        push_notifications = await PushNotification.objects().where(
            PushNotification.telegram_chat_id == telegram_chat_id
        )
        ret = []
        for current in PushNotificationTypeEnum:
            persisted = next(
                filter(
                    lambda n: PushNotificationTypeEnum.from_value(n.notification_type) == current, push_notifications
                ),
                None,
            )
            ret.append(
                PushNotificationItem(
                    telegram_chat_id=telegram_chat_id,
                    notification_type=current,
                    activated=persisted is not None and persisted.activated,
                )
            )
        return ret

    async def toggle_push_notification_by_type(
        self, telegram_chat_id: int, notification_type: PushNotificationTypeEnum
    ) -> PushNotificationItem:
        push_notification = (
            await PushNotification.objects()
            .where(PushNotification.telegram_chat_id == telegram_chat_id)
            .where(PushNotification.notification_type == notification_type.value)
            .first()
        )
        if push_notification:
            push_notification.activated = not push_notification.activated
        else:
            push_notification = PushNotification(
                telegram_chat_id=telegram_chat_id, notification_type=notification_type.value, activated=True
            )
        await push_notification.save()
        ret = PushNotificationItem(
            telegram_chat_id=push_notification.telegram_chat_id,
            notification_type=PushNotificationTypeEnum.from_value(push_notification.notification_type),
            activated=push_notification.activated,
        )
        return ret

    async def get_actived_subscription_by_type(self, notification_type: PushNotificationTypeEnum) -> list[int]:
        push_notifications = (
            await PushNotification.objects()
            .where(PushNotification.notification_type == notification_type.value)
            .where(PushNotification.activated.eq(True))
        )
        ret = [push_notification.telegram_chat_id for push_notification in push_notifications]
        return ret
