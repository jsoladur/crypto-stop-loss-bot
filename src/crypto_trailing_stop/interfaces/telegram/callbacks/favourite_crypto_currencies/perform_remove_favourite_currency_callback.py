import logging
import re

from aiogram import F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
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

REGEX = r"^perform_remove_favourite_currency\$\$(.+)$"


@dp.callback_query(F.data.regexp(REGEX))
async def perform_remove_favourite_currency_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            match = re.match(REGEX, callback_query.data)
            currency = match.group(1)
            await favourite_crypto_currency_service.remove(currency)
            await callback_query.message.answer(
                f"ℹ️ {html.bold(currency)} crypto currency has been removed from your favourites.",
                reply_markup=keyboards_builder.get_home_keyboard(),
            )
        except Exception as e:
            logger.error(f"Error removing the selected crypto currency: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while removing the selected crypto currency. Please try again later:\n\n{html.code(format_exception(e))}"  # noqa: E501
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to operate with favourites crypto currencies.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
