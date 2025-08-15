import logging
import re
from html import escape as html_escape

from aiogram import F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.services.auto_entry_trader_event_handler_service import (
    AutoEntryTraderEventHandlerService,
)
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
auto_entry_trader_event_handler_service = AutoEntryTraderEventHandlerService()


@dp.callback_query(F.data.regexp(r"^trigger_auto_entry_trader\$\$(.+)$"))
async def trigger_auto_entry_trader_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            match = re.match(r"^trigger_auto_entry_trader\$\$(.+)$", callback_query.data)
            symbol = match.group(1)
            await auto_entry_trader_event_handler_service.trigger_immediate_buy_market_signal(symbol)
            await callback_query.message.answer(
                f"ℹ️ Auto-Entry Trader has been successfully triggered for {symbol}. "
                + "You will receive a push notification once the operations are completed.",
                reply_markup=keyboards_builder.get_home_keyboard(),
            )
        except Exception as e:
            logger.error(f"Error triggering Auto-Entry Trader: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                "⚠️ An error occurred while triggering Auto-Entry Trader"
                + f"Please try again later:\n\n{html.code(html_escape(str(e)))}"
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to manual trigger Auto-Entry Trader.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
