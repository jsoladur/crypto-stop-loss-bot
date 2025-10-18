import logging
import re

from aiogram import Dispatcher, F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange import AbstractOperatingExchangeService
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
operating_exchange_service: AbstractOperatingExchangeService = (
    application_container.infrastructure_container().adapters_container().operating_exchange_service()
)


@dp.callback_query(F.data.regexp(r"^choose_sell_percent\$\$(.+)$"))
async def choose_sell_percent_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            match = re.match(r"^choose_sell_percent\$\$(.+)$", callback_query.data)
            sell_order_id = match.group(1)
            sell_order = await operating_exchange_service.get_order_by_id(sell_order_id)
            crypto_currency, *_ = sell_order.symbol.split("/")
            formatted_order_ammount = html.bold(f"{sell_order.order_amount} {crypto_currency}")
            await callback_query.message.answer(
                f"ℹ️ Choose from {formatted_order_ammount} the percent amount of {crypto_currency} you want to sell. ",
                reply_markup=keyboards_builder.get_choose_sell_percent_keyboard(sell_order_id),
            )
        except Exception as e:
            logger.error(f"Error triggering Auto-Entry Trader: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                "⚠️ An error occurred while triggering immediate sell order."
                + f"Please try again later:\n\n{html.code(format_exception(e))}"
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to manual trigger immediate sell order.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
