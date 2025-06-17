import logging
from aiogram.types import CallbackQuery
from aiogram import html
from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.infrastructure.services import (
    SessionStorageService,
    GlobalSummaryService,
)
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
global_summary_service = GlobalSummaryService()


@dp.callback_query(lambda c: c.data == "get_global_summary")
async def set_stop_loss_percentage_callback_handler(
    callback_query: CallbackQuery, state: FSMContext
) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            global_summary = await global_summary_service.get_global_summary()
            message = "=========================="
            message += "BIT2ME GLOBAL SUMMARY"
            message += "=========================="
            message += f"TOTAL DEPOSIT: {global_summary.total_deposits:.2f} EUR"
            message += f"WITHDRAWALS: {global_summary.withdrawls:.2f} EUR"
            message += f"CURRENT: {global_summary.current_value:.2f} EUR"
            message += "----------------"
            message += f"NET REVENUE: {((global_summary.current_value - global_summary.total_deposits) + global_summary.withdrawls):.2f} EUR"
            message += "=========================="
            await callback_query.message.answer(message)
        except Exception as e:
            logger.error(f"Error fetching global summary: {str(e)}")
            await callback_query.message.answer(
                f"An error occurred while fetching the global summary. Please try again later:\n\n{html.code(str(e))}"
            )
    else:
        await callback_query.message.answer(
            "Please log in to get the global summary.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
