import logging

from aiogram import html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
crypto_analytics_service = CryptoAnalyticsService(
    bit2me_remote_service=Bit2MeRemoteService(), ccxt_remote_service=CcxtRemoteService()
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
                f"⚠️ An error occurred while retrieving favourite symbols. Please try again later:\n\n{html.code(str(e))}"  # noqa: E501
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to get current crypto metrics.", reply_markup=keyboards_builder.get_login_keyboard(state)
        )
