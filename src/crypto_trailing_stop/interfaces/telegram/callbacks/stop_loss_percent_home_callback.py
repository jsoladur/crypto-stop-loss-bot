import logging

from aiogram import html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.infrastructure.services.stop_loss_percent_service import StopLossPercentService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
stop_loss_percent_service = StopLossPercentService(
    bit2me_remote_service=Bit2MeRemoteService(), global_flag_service=GlobalFlagService()
)


@dp.callback_query(lambda c: c.data == "stop_loss_percent_home")
async def stop_loss_percent_home_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            stop_loss_percent_items = await stop_loss_percent_service.find_all_stop_loss_percent()
            await callback_query.message.answer(
                "ℹ Click into a symbol for changing its stop loss percent value",
                reply_markup=keyboards_builder.get_stop_loss_percent_items_keyboard(stop_loss_percent_items),
            )
        except Exception as e:
            logger.error(f"Error retrieving stop loss items: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while retrieving stop loss items. Please try again later:\n\n{html.code(str(e))}"
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to set the stop loss percent (%).",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
