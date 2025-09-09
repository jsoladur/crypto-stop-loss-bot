import logging
import re

from aiogram import F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.services.limit_sell_order_guard_cache_service import (
    LimitSellOrderGuardCacheService,
)
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.infrastructure.services.vo.immediate_sell_order_item import ImmediateSellOrderItem
from crypto_trailing_stop.interfaces.telegram.exception_utils import format_exception
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
bit2_me_remote_service = Bit2MeRemoteService()
limit_sell_order_guard_cache_service = LimitSellOrderGuardCacheService()

REGEX = r"^trigger_sell_now\$\$(.+)\$\$(.+)$"


@dp.callback_query(F.data.regexp(REGEX))
async def trigger_sell_now_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            match = re.match(REGEX, callback_query.data)
            sell_order_id = match.group(1)
            sell_percent = float(match.group(2))
            sell_order = await bit2_me_remote_service.get_order_by_id(sell_order_id)
            crypto_currency, *_ = sell_order.symbol.split("/")
            limit_sell_order_guard_cache_service.mark_immediate_sell_order(
                ImmediateSellOrderItem(sell_order_id=sell_order_id, percent_to_sell=sell_percent)
            )
            formatted_order_ammount = html.bold(f"{sell_order.order_amount} {crypto_currency}")
            await callback_query.message.answer(
                f"ℹ️ {html.bold(sell_percent)}% OF {formatted_order_ammount} MARKED TO IMMEDIATE SELL. "
                + "You will receive a push notification once the Limit Sell Guard has completed the trade.",
                reply_markup=keyboards_builder.get_home_keyboard(),
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
