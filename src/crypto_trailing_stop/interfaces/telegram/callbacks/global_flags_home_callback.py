import logging
from aiogram.types import CallbackQuery
from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.infrastructure.services import (
    SessionStorageService,
    StopLossPercentService,
)
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
stop_loss_percent_service = StopLossPercentService()
keyboards_builder = KeyboardsBuilder()


@dp.callback_query(lambda c: c.data == "stop_loss_percent_home")
async def stop_loss_percent_home_callback_handler(
    callback_query: CallbackQuery, state: FSMContext
) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        await callback_query.message.answer(
            "⚠️ Feature under construction!",
        )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to set the stop loss percent (%).",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
