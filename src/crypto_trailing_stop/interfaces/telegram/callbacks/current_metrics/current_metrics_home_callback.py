import logging

from aiogram import Dispatcher, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.favourite_crypto_currency_service import (
    FavouriteCryptoCurrencyService,
)
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.exception_utils import format_exception
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

application_container = get_application_container()
dp: Dispatcher = application_container.dispatcher()
session_storage_service: SessionStorageService = application_container.session_storage_service()
keyboards_builder: KeyboardsBuilder = (
    application_container.interfaces_container().telegram_container().keyboards_builder()
)
favourite_crypto_currency_service: FavouriteCryptoCurrencyService = (
    application_container.infrastructure_container().services_container().favourite_crypto_currency_service()
)
crypto_analytics_service: CryptoAnalyticsService = (
    application_container.infrastructure_container().services_container().crypto_analytics_service()
)


@dp.callback_query(lambda c: c.data == "current_metrics_home")
async def current_metrics_home_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            items = await crypto_analytics_service.get_favourite_symbols()
            await callback_query.message.answer(
                "ℹ️ Click into a symbol for getting its current crypto metrics.",
                reply_markup=keyboards_builder.get_current_metrics_home_keyboard(items),
            )
        except Exception as e:
            logger.error(f"Error retrieving favourite symbols: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while retrieving favourite symbols. Please try again later:\n\n{html.code(format_exception(e))}"  # noqa: E501
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to get current crypto metrics.", reply_markup=keyboards_builder.get_login_keyboard(state)
        )
