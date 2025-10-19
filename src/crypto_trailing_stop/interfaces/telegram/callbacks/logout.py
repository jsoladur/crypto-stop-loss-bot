import logging

from aiogram import Dispatcher, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

application_container = get_application_container()
dp: Dispatcher = application_container.interfaces_container().telegram_container().dispatcher()
session_storage_service: SessionStorageService = (
    application_container.interfaces_container().telegram_container().session_storage_service()
)
keyboards_builder: KeyboardsBuilder = (
    application_container.interfaces_container().telegram_container().keyboards_builder()
)


@dp.callback_query(lambda c: c.data == "logout")
async def logout_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    await session_storage_service.perform_logout(state)
    await callback_query.message.answer(
        f"Goodbye, {html.bold(callback_query.from_user.full_name)}! You have been logged out.",
        reply_markup=keyboards_builder.get_login_keyboard(state),
    )
