import logging
import re

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()


@dp.callback_query(F.data.regexp(r"^immediate_sell_limit_order\$\$(.+)$"))
async def immediate_sell_limit_order_confirmation_callback_handler(
    callback_query: CallbackQuery, state: FSMContext
) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        match = re.match(r"^immediate_sell_limit_order\$\$(.+)$", callback_query.data)
        sell_order_id = match.group(1)
        await callback_query.message.answer(
            "🛑 CONFIRM ACTION: IMMEDIATE SELL LIMIT ORDER. This operation CANNOT be undone. "
            + "Are you SURE you want to PROCEED?",
            reply_markup=keyboards_builder.get_yes_no_keyboard(
                yes_button_callback_data=f"trigger_immediate_sell$${sell_order_id}"
            ),
        )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to manual trigger Sell Limit Order.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
