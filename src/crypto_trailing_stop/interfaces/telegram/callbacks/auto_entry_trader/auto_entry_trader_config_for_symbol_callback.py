import logging
import re

from aiogram import Dispatcher, F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.services.auto_buy_trader_config_service import AutoBuyTraderConfigService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

application_container = get_application_container()
dp: Dispatcher = application_container.dispatcher()
session_storage_service: SessionStorageService = application_container.session_storage_service()
keyboards_builder: KeyboardsBuilder = (
    application_container.interfaces_container().telegram_container().keyboards_builder()
)
auto_buy_trader_config_service: AutoBuyTraderConfigService = (
    application_container.infrastructure_container().services_container().auto_buy_trader_config_service()
)


@dp.callback_query(F.data.regexp(r"^set_auto_entry_trader_config\$\$(.+)$"))
async def auto_entry_trader_config_for_symbol_callback_handler(
    callback_query: CallbackQuery, state: FSMContext
) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        match = re.match(r"^set_auto_entry_trader_config\$\$(.+)$", callback_query.data)
        symbol = match.group(1)
        await callback_query.message.answer(
            "ℹ️ Select the 💰 FIAT 💰 wallet amount assigned "
            + f"for {html.bold(symbol.upper())} Auto-Entry Trader executions, "
            + "where 0% would mean disabled.",
            reply_markup=keyboards_builder.get_auto_entry_trader_config_values_by_symbol_keyboard(symbol),
        )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to set 💰 FIAT 💰 assignations for the Auto-Entry Trader.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
