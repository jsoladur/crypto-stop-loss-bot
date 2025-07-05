import logging

from aiogram import html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.services.market_signal_service import MarketSignalService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
market_signal_service = MarketSignalService()


@dp.callback_query(lambda c: c.data == "last_market_signals")
async def last_market_signals_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            await callback_query.message.answer("👷🚧 In construction... This feature will be available soon!")
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
