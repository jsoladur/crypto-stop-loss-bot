import logging
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.infrastructure.services import SessionStorageService
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()


@dp.callback_query(lambda c: c.data == "set_stop_loss_percentage")
async def set_stop_loss_percentage_callback_handler(
    callback_query: CallbackQuery, state: FSMContext
) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        # FIXME: To be implemented!
        await callback_query.message.answer(
            "🚧🚧 The functionality to set stop loss percentage is not implemented yet 🚧🚧"
        )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to set the stop loss percentage.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
