import logging
import re
from html import escape as html_escape

from aiogram import F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher, get_telegram_bot
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.callbacks.buy_sell_signals_config.buy_sell_signals_config_form import (
    BuySellSignalsConfigForm,
)
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.interfaces.telegram.messages_formatter import MessagesFormatter

logger = logging.getLogger(__name__)

dp = get_dispacher()
bot = get_telegram_bot()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
messages_formatter = MessagesFormatter()
buy_sell_signals_config_service = BuySellSignalsConfigService(bit2me_remote_service=Bit2MeRemoteService())


@BuySellSignalsConfigForm.submit(router=dp)
async def buy_sell_signals_config_form_submit_handler(form: BuySellSignalsConfigForm):
    try:
        symbol = await session_storage_service.get_buy_sell_signals_symbol_form(form.chat_id)
        item = form.to_persistable(symbol)
        await buy_sell_signals_config_service.save_or_update(item)
        message = f"✅ Buy/Sell signals for {html.bold(symbol)} configuration successfully persisted.\n\n"
        message += messages_formatter.format_buy_sell_signals_config_message(item)
        await form.answer(message, reply_markup=keyboards_builder.get_home_keyboard())
    except Exception as e:
        logger.error(f"Error persisting Buy/Sell signals config: {str(e)}", exc_info=True)
        await form.answer(
            "⚠️ An error occurred while persisting an Buy/Sell signals configuration. "
            + f"Please try again later:\n\n{html.code(html_escape(str(e)))}"
        )


@dp.callback_query(F.data.regexp(r"^persist_buy_sell_signals_config\$\$(.+)$"))
async def persist_buy_sell_signals_config_callback_handler(callback_query: CallbackQuery, state: FSMContext):
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            match = re.match(r"^persist_buy_sell_signals_config\$\$(.+)$", callback_query.data)
            symbol = match.group(1).strip().upper()
            await session_storage_service.set_buy_sell_signals_symbol_form(state, symbol)
            await BuySellSignalsConfigForm.start(bot, state)
        except Exception as e:
            logger.error(f"Error persisting Buy/Sell signals config: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                "⚠️ An error occurred while persisting an Buy/Sell signals configuration. "
                + f"Please try again later:\n\n{html.code(html_escape(str(e)))}"
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to set the corresponding Buy/Sell signals configuration.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
