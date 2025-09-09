import logging
import re

from aiogram import F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.exception_utils import format_exception
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
bit2_me_remote_service = Bit2MeRemoteService()


@dp.callback_query(F.data.regexp(r"^choose_sell_percent\$\$(.+)$"))
async def choose_sell_percent_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            match = re.match(r"^choose_sell_percent\$\$(.+)$", callback_query.data)
            sell_order_id = match.group(1)
            sell_order = await bit2_me_remote_service.get_order_by_id(sell_order_id)
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
