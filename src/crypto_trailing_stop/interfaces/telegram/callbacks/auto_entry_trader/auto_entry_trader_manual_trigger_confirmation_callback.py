import logging
import re

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_dispacher
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()


@dp.callback_query(F.data.regexp(r"^auto_entry_trader_manual_trigger_confirmation\$\$(.+)$"))
async def auto_entry_trader_manual_trigger_confirmation_callback_handler(
    callback_query: CallbackQuery, state: FSMContext
) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        match = re.match(r"^auto_entry_trader_manual_trigger_confirmation\$\$(.+)$", callback_query.data)
        symbol = match.group(1)
        await callback_query.message.answer(
            "🛑 CONFIRM ACTION: This operation CANNOT be undone. Are you SURE you want to PROCEED?",
            reply_markup=keyboards_builder.get_yes_no_keyboard(
                yes_button_callback_data=f"trigger_auto_entry_trader$${symbol}"
            ),
        )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to manual trigger Auto-Entry Trader.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
