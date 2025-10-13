import logging

from aiogram import html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager, StartMode

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.callbacks.favourite_crypto_currencies.dialog import (
    FavouriteCryptoCurrencyStates,
)
from crypto_trailing_stop.interfaces.telegram.exception_utils import format_exception
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()


@dp.callback_query(lambda c: c.data == "add_favourite_crypto_currency")
async def add_favourite_crypto_currency_callback_handler(
    callback_query: CallbackQuery, state: FSMContext, dialog_manager: DialogManager
) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            await dialog_manager.start(FavouriteCryptoCurrencyStates.main, mode=StartMode.RESET_STACK)
        except Exception as e:
            logger.error(f"Error retrieving non favourites crypto currencies: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while retrieving non favourites crypto currencies. Please try again later:\n\n{html.code(format_exception(e))}"  # noqa: E501
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to operate with favourites crypto currencies.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
