import logging

from aiogram import Dispatcher
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


@dp.callback_query(lambda c: c.data == "set_risk_percent")
async def set_stop_loss_percent_for_symbol_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        await callback_query.message.answer(
            "ℹ️ Select the new Risk Percent to apply", reply_markup=keyboards_builder.get_risk_percent_values()
        )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to set the risk management percent value (%).",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
