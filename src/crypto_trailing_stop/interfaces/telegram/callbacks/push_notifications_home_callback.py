import logging

from aiogram import html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.services import PushNotificationService, SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
push_notification_service = PushNotificationService()


@dp.callback_query(lambda c: c.data == "push_notificacions_home")
async def push_notifications_home_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            push_notification_items = await push_notification_service.find_push_notification_by_telegram_chat_id(
                state.key.chat_id
            )
            await callback_query.message.answer(
                "ℹ Click into a notification type for toggling (enabled/disabled) them",
                reply_markup=keyboards_builder.get_push_notifications_home_keyboard(push_notification_items),
            )
        except Exception as e:
            logger.error(
                f"Error trying to retrieve push notifications configured for this chat: {str(e)}", exc_info=True
            )
            await callback_query.message.answer(
                "⚠️ An error occurred while retrieving push notifications items. "
                + f"Please try again later:\n\n{html.code(str(e))}"
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to operate along with Push notifications.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
