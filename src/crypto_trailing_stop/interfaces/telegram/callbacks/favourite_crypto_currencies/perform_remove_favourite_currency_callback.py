import logging
import re

from aiogram import Dispatcher, F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.services.favourite_crypto_currency_service import (
    FavouriteCryptoCurrencyService,
)
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.exception_utils import format_exception
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

application_container = get_application_container()
dp: Dispatcher = application_container.interfaces_container().telegram_container().dispatcher()
session_storage_service: SessionStorageService = (
    application_container.interfaces_container().telegram_container().session_storage_service()
)
keyboards_builder: KeyboardsBuilder = (
    application_container.interfaces_container().telegram_container().keyboards_builder()
)
favourite_crypto_currency_service: FavouriteCryptoCurrencyService = (
    application_container.infrastructure_container().services_container().favourite_crypto_currency_service()
)

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
