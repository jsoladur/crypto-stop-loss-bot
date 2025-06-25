import logging
from aiogram.types import CallbackQuery
from aiogram import F, html

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.infrastructure.services import (
    SessionStorageService,
    GlobalFlagService,
)
from crypto_trailing_stop.infrastructure.services.enums import GlobalFlagTypeEnum
from aiogram.fsm.context import FSMContext
import re

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
global_flag_service = GlobalFlagService()
keyboards_builder = KeyboardsBuilder()


@dp.callback_query(F.data.regexp(r"^toggle_global_flag\$\$(.+)$"))
async def toggle_push_notification_callback_handler(
    callback_query: CallbackQuery, state: FSMContext
) -> None:
    # FIXME: Uncomment this!
    # is_user_logged = await session_storage_service.is_user_logged(state)
    is_user_logged = True
    if is_user_logged:
        try:
            match = re.match(r"^toggle_global_flag\$\$(.+)$", callback_query.data)
            global_flag_name = GlobalFlagTypeEnum.from_value(match.group(1))
            global_flag_item = await global_flag_service.toggle_by_name(
                global_flag_name
            )
            await callback_query.message.answer(
                f"ℹ Global Flag for '{html.bold(global_flag_item.name.description)}'"
                + f" has been {('🟢' + html.bold(' ENABLED')) if global_flag_item.value else ('🟥' + html.bold(' DISABLED'))}!",
                reply_markup=keyboards_builder.get_home_keyboard(),
            )
        except Exception as e:
            logger.error(
                f"Error trying to toggle push notifications for this chat: {str(e)}"
            )
            await callback_query.message.answer(
                f"⚠️ An error occurred while toggling push notifications. Please try again later:\n\n{html.code(str(e))}"
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to operate with Global Flags.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
