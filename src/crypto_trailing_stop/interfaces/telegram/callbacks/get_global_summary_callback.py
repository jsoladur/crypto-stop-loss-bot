import logging

from aiogram import Dispatcher, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.services.global_summary_service import GlobalSummaryService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.exception_utils import format_exception
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.interfaces.telegram.messages_formatter import MessagesFormatter

logger = logging.getLogger(__name__)

application_container = get_application_container()
dp: Dispatcher = application_container.interfaces_container().telegram_container().dispatcher()
session_storage_service: SessionStorageService = (
    application_container.interfaces_container().telegram_container().session_storage_service()
)
keyboards_builder: KeyboardsBuilder = (
    application_container.interfaces_container().telegram_container().keyboards_builder()
)
messages_formatter: MessagesFormatter = (
    application_container.interfaces_container().telegram_container().messages_formatter()
)
global_summary_service: GlobalSummaryService = (
    application_container.infrastructure_container().services_container().global_summary_service()
)


@dp.callback_query(lambda c: c.data == "get_global_summary")
async def set_stop_loss_percent_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            global_summary = await global_summary_service.get_global_summary()
            message = messages_formatter.format_global_summary(global_summary)
            await callback_query.message.answer(text=message)
        except Exception as e:
            logger.error(f"Error fetching global summary: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while fetching the global summary. Please try again later:\n\n{html.code(format_exception(e))}"  # noqa: E501
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to get the global summary.", reply_markup=keyboards_builder.get_login_keyboard(state)
        )
