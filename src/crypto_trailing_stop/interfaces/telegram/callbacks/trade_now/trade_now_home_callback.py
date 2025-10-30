import logging

from aiogram import Dispatcher, html
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


@dp.callback_query(lambda c: c.data == "trade_now_home")
async def trade_now_home_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            favourite_crypto_currencies = await favourite_crypto_currency_service.find_all()
            await callback_query.message.answer(
                "ℹ️ Select a crypto to trade it now!.",
                reply_markup=keyboards_builder.get_trade_now_keyboard(favourite_crypto_currencies),
            )
        except Exception as e:
            logger.error(f"Error retrieving favourites crypto currencies: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while retrieving favourites crypto currencies. Please try again later:\n\n{html.code(format_exception(e))}"  # noqa: E501
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to use trade now hints and leverage features.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
