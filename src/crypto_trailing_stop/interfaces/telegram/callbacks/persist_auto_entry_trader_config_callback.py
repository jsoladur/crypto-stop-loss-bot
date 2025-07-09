import logging
import re

from aiogram import F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.services.auto_buy_trader_config_service import AutoBuyTraderConfigService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.infrastructure.services.vo.auto_buy_trader_config_item import AutoBuyTraderConfigItem
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.interfaces.telegram.messages_formatter import MessagesFormatter

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
messages_formatter = MessagesFormatter()
auto_buy_trader_config_service = AutoBuyTraderConfigService(bit2me_remote_service=Bit2MeRemoteService())


@dp.callback_query(F.data.regexp(r"^persist_auto_entry_trader_config\$\$(.+?)\$\$(.+)$"))
async def handle_persist_stop_loss_callback(callback_query: CallbackQuery, state: FSMContext):
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            match = re.match(r"^persist_auto_entry_trader_config\$\$(.+?)\$\$(.+)$", callback_query.data)
            symbol = match.group(1).strip().upper()
            percent_value = int(match.group(2).strip())
            await auto_buy_trader_config_service.save_or_update(
                AutoBuyTraderConfigItem(symbol=symbol, fiat_wallet_percent_assigned=percent_value)
            )
            answer_text = (
                f"ℹ️ 💰 FIAT 💰 assigned value for {html.bold(symbol)} at {html.bold(str(percent_value) + '%')} "
                + "has been successfully applied! \n\n"
            )
            await callback_query.message.answer(answer_text, reply_markup=keyboards_builder.get_home_keyboard())
        except Exception as e:
            logger.error(f"Error persisting Auto-Entry trader config: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                "⚠️ An error occurred while persisting an Auto-Entry Trader configuration. "
                + f"Please try again later:\n\n{html.code(str(e))}"
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to set the corresponding Auto-Entry Trader configuration.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
