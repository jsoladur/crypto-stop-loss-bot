import logging
from abc import ABC
from html import escape as html_escape

from aiogram import html

from crypto_trailing_stop.infrastructure.services.enums import PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.push_notification_service import PushNotificationService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.interfaces.telegram.services.telegram_service import TelegramService

logger = logging.getLogger(__name__)


class AbstractService(ABC):
    def __init__(self) -> None:
        self._push_notification_service = PushNotificationService()
        self._telegram_service = TelegramService(
            session_storage_service=SessionStorageService(), keyboards_builder=KeyboardsBuilder()
        )

    async def _notify_alert_by_type(self, notification_type: PushNotificationTypeEnum, message: str) -> None:
        telegram_chat_ids = await self._push_notification_service.get_actived_subscription_by_type(
            notification_type=notification_type
        )
        for tg_chat_id in telegram_chat_ids:
            await self._telegram_service.send_message(chat_id=tg_chat_id, text=message)

    async def _notify_fatal_error_via_telegram(self, e: Exception) -> None:
        exception_text = f"{e.__class__.__name__} :: {str(e)}" if str(e) else e.__class__.__name__
        try:
            telegram_chat_ids = await self._push_notification_service.get_actived_subscription_by_type(
                notification_type=PushNotificationTypeEnum.BACKGROUND_JOB_FALTAL_ERRORS
            )
            for tg_chat_id in telegram_chat_ids:
                await self._telegram_service.send_message(
                    chat_id=tg_chat_id,
                    text=f"⚠️ [{self.__class__.__name__}] FATAL ERROR occurred! "
                    + f"Please try again later:\n\n{html.code(html_escape(exception_text))}",
                )
        except Exception as e:
            logger.warning(f"Unexpected error, notifying fatal error via Telegram: {exception_text}", exc_info=True)
