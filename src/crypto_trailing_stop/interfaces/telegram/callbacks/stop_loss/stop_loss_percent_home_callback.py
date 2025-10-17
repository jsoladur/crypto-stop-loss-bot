import logging

from aiogram import Dispatcher, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.infrastructure.services.stop_loss_percent_service import StopLossPercentService
from crypto_trailing_stop.interfaces.telegram.exception_utils import format_exception
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

application_container = get_application_container()
dp: Dispatcher = application_container.dispatcher()
session_storage_service: SessionStorageService = application_container.session_storage_service()
keyboards_builder: KeyboardsBuilder = (
    application_container.interfaces_container().telegram_container().keyboards_builder()
)
stop_loss_percent_service: StopLossPercentService = (
    application_container.infrastructure_container().services_container().stop_loss_percent_service()
)


@dp.callback_query(lambda c: c.data == "stop_loss_percent_home")
async def stop_loss_percent_home_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            stop_loss_percent_items = await stop_loss_percent_service.find_all()
            await callback_query.message.answer(
                "ℹ️ Click into a symbol for changing its stop loss percent value",
                reply_markup=keyboards_builder.get_stop_loss_percent_items_keyboard(stop_loss_percent_items),
            )
        except Exception as e:
            logger.error(f"Error retrieving stop loss items: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while retrieving stop loss items. Please try again later:\n\n{html.code(format_exception(e))}"  # noqa: E501
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to set the stop loss percent (%).",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
