import logging
from aiogram import html
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.infrastructure.services import SessionStorageService
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()


@dp.callback_query(lambda c: c.data == "logout")
async def logout_callback_handler(
    callback_query: CallbackQuery, state: FSMContext
) -> None:
    await session_storage_service.perform_logout(state)
    await callback_query.message.answer(
        f"Goodbye, {html.bold(callback_query.message.from_user.full_name)}! You have been logged out.",
        reply_markup=keyboards_builder.get_login_keyboard(state),
    )
