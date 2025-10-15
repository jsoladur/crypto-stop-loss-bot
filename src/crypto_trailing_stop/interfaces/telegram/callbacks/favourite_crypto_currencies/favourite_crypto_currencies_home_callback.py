import logging

from aiogram import html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_dispacher
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.services.favourite_crypto_currency_service import (
    FavouriteCryptoCurrencyService,
)
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.exception_utils import format_exception
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
favourite_crypto_currency_service = FavouriteCryptoCurrencyService(bit2me_remote_service=Bit2MeRemoteService())


@dp.callback_query(lambda c: c.data == "favourite_crypto_currencies_home")
async def favourite_crypto_currencies_home_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            favourite_crypto_currencies = await favourite_crypto_currency_service.find_all()
            await callback_query.message.answer(
                "ℹ️ Select a crypto currency to remove as favourite or add a new one.",
                reply_markup=keyboards_builder.get_favourite_crypto_currencies_keyboard(favourite_crypto_currencies),
            )
        except Exception as e:
            logger.error(f"Error retrieving favourites crypto currencies: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while retrieving favourites crypto currencies. Please try again later:\n\n{html.code(format_exception(e))}"  # noqa: E501
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to operate with favourites crypto currencies.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
