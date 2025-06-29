import logging

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.services import GlobalFlagService, SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
global_flag_service = GlobalFlagService()


@dp.callback_query(lambda c: c.data == "global_flags_home")
async def stop_loss_percent_home_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        global_flag_items = await global_flag_service.find_all()
        await callback_query.message.answer(
            "ℹ Click into a flag to active/deactivate them",
            reply_markup=keyboards_builder.get_global_flags_home_keyboard(global_flag_items),
        )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to operate with Global Flags.", reply_markup=keyboards_builder.get_login_keyboard(state)
        )
