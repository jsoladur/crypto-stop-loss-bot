import logging
import re
from html import escape as html_escape

from aiogram import F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
global_flag_service = GlobalFlagService()


@dp.callback_query(F.data.regexp(r"^toggle_global_flag\$\$(.+)$"))
async def toggle_push_notification_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            match = re.match(r"^toggle_global_flag\$\$(.+)$", callback_query.data)
            global_flag_name = GlobalFlagTypeEnum.from_value(match.group(1))
            global_flag_item = await global_flag_service.toggle_by_name(global_flag_name)
            await callback_query.message.answer(
                f"ℹ️ Global Flag for '{html.bold(global_flag_item.name.description)}'"
                + f" has been {('🟢' + html.bold(' ENABLED')) if global_flag_item.value else ('🟥' + html.bold(' DISABLED'))}!",  # noqa: E501
                reply_markup=keyboards_builder.get_home_keyboard(),
            )
        except Exception as e:
            logger.error(f"Error trying to toggle push notifications for this chat: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while toggling push notifications. Please try again later:\n\n{html.code(html_escape(str(e)))}"  # noqa: E501
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to operate with Global Flags.", reply_markup=keyboards_builder.get_login_keyboard(state)
        )
