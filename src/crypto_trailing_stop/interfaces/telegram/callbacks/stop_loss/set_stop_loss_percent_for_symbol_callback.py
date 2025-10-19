import logging
import re

from aiogram import Dispatcher, F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.infrastructure.services.stop_loss_percent_service import StopLossPercentService
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
stop_loss_percent_service: StopLossPercentService = (
    application_container.infrastructure_container().services_container().stop_loss_percent_service()
)


@dp.callback_query(F.data.regexp(r"^set_stop_loss_percent\$\$(.+)$"))
async def set_stop_loss_percent_for_symbol_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        match = re.match(r"^set_stop_loss_percent\$\$(.+)$", callback_query.data)
        symbol = match.group(1)
        await callback_query.message.answer(
            f"ℹ️ Select the new Stop Loss Percent for {html.bold(symbol.upper())}",
            reply_markup=keyboards_builder.get_stop_loss_percent_values_by_symbol_keyboard(symbol),
        )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to set the stop loss percent (%).",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
