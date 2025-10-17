import logging

from aiogram import Dispatcher, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.services.global_flag_service import GlobalFlagService
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
global_flag_service: GlobalFlagService = (
    application_container.infrastructure_container().services_container().global_flag_service()
)


@dp.callback_query(lambda c: c.data == "global_flags_home")
async def stop_loss_percent_home_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            global_flag_items = await global_flag_service.find_all()
            await callback_query.message.answer(
                "ℹ️ Click into a flag to active/deactivate them",
                reply_markup=keyboards_builder.get_global_flags_home_keyboard(global_flag_items),
            )
        except Exception as e:
            logger.error(f"Error trying to retrieve global flags: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while retrieving global flags. Please try again later:\n\n{html.code(format_exception(e))}"  # noqa: E501
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to operate with Global Flags.", reply_markup=keyboards_builder.get_login_keyboard(state)
        )
