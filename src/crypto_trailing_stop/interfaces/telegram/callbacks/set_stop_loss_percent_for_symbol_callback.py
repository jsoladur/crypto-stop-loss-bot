import logging
import re

from aiogram import F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.services import (
    GlobalFlagService,
    SessionStorageService,
    StopLossPercentService,
)
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
stop_loss_percent_service = StopLossPercentService(
    bit2me_remote_service=Bit2MeRemoteService(), global_flag_service=GlobalFlagService()
)


@dp.callback_query(F.data.regexp(r"^set_stop_loss_percent\$\$(.+)$"))
async def set_stop_loss_percent_for_symbol_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        match = re.match(r"^set_stop_loss_percent\$\$(.+)$", callback_query.data)
        symbol = match.group(1)
        await callback_query.message.answer(
            f"ℹ Select the new Stop Loss Percent for {html.bold(symbol.upper())}",
            reply_markup=keyboards_builder.get_stop_loss_percent_values_by_symbol_keyboard(symbol),
        )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to set the stop loss percent (%).",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
