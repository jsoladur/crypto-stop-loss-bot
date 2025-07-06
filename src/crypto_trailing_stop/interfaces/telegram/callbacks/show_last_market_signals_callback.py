import logging
import re

from aiogram import F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.services.market_signal_service import MarketSignalService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.interfaces.telegram.messages_formatter import MessagesFormatter

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
messages_formatter = MessagesFormatter()
market_signal_service = MarketSignalService()


@dp.callback_query(F.data.regexp(r"^show_last_market_signals\$\$(.+)$"))
async def show_last_market_signals_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            match = re.match(r"^show_last_market_signals\$\$(.+)$", callback_query.data)
            symbol = match.group(1)
            market_signals = await market_signal_service.find_by_symbol(symbol)
            message = messages_formatter.format_market_signals_message(symbol, market_signals)
            await callback_query.message.answer(message)
        except Exception as e:
            logger.error(f"Error fetching last market signals: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                "⚠️ An error occurred while fetching last market signals. "
                + f"Please try again later:\n\n{html.code(str(e))}"
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to fetch the last market signals.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
