import logging
import re

from aiogram import F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.services.auto_buy_trader_config_service import AutoBuyTraderConfigService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
auto_buy_trader_config_service = AutoBuyTraderConfigService(bit2me_remote_service=Bit2MeRemoteService())


@dp.callback_query(F.data.regexp(r"^set_auto_entry_trader_config\$\$(.+)$"))
async def auto_entry_trader_config_for_symbol_callback_handler(
    callback_query: CallbackQuery, state: FSMContext
) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        match = re.match(r"^set_auto_entry_trader_config\$\$(.+)$", callback_query.data)
        symbol = match.group(1)
        await callback_query.message.answer(
            f"ℹ Select the new 💰 FIAT 💰 assigned value for {html.bold(symbol.upper())} auto-entries executions",
            reply_markup=keyboards_builder.get_auto_entry_trader_config_values_by_symbol_keyboard(symbol),
        )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to set 💰 FIAT 💰 assignations for the Auto-Entry Trader.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
