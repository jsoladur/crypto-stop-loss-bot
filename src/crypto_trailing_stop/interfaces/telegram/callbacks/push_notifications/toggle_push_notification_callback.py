import logging
import re

from aiogram import F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_dispacher
from crypto_trailing_stop.infrastructure.services.enums import PushNotificationTypeEnum
from crypto_trailing_stop.infrastructure.services.push_notification_service import PushNotificationService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.exception_utils import format_exception
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
push_notification_service = PushNotificationService()


@dp.callback_query(F.data.regexp(r"^toggle_push_notification\$\$(.+)$"))
async def toggle_push_notification_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            match = re.match(r"^toggle_push_notification\$\$(.+)$", callback_query.data)
            notification_type = PushNotificationTypeEnum.from_value(match.group(1))
            push_notification_item = await push_notification_service.toggle_push_notification_by_type(
                telegram_chat_id=state.key.chat_id, notification_type=notification_type
            )
            await callback_query.message.answer(
                f"ℹ️ Push notifications for '{html.bold(push_notification_item.notification_type.description)}'"
                + f" has been {('🔔' + html.bold(' ENABLED')) if push_notification_item.activated else ('🔕' + html.bold(' DISABLED'))}!",  # noqa: E501
                reply_markup=keyboards_builder.get_home_keyboard(),
            )
        except Exception as e:
            logger.error(f"Error trying to toggle push notifications for this chat: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while toggling push notifications. Please try again later:\n\n{html.code(format_exception(e))}"  # noqa: E501
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to operate with Push Notifications configuration.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
