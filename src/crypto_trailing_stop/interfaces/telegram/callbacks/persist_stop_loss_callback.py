import logging
from aiogram.types import CallbackQuery
from aiogram import F, html

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.infrastructure.services import (
    SessionStorageService,
    StopLossPercentService,
)
from crypto_trailing_stop.infrastructure.services.vo.stop_loss_percent_item import (
    StopLossPercentItem,
)
from aiogram.fsm.context import FSMContext
import re

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
stop_loss_percent_service = StopLossPercentService()
keyboards_builder = KeyboardsBuilder()


@dp.callback_query(F.data.regexp(r"^persist_stop_loss\$\$(.+?)\$\$(.+)$"))
async def handle_persist_stop_loss_callback(
    callback_query: CallbackQuery, state: FSMContext
):
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            match = re.match(
                r"^persist_stop_loss\$\$(.+?)\$\$(.+)$", callback_query.data
            )
            symbol = match.group(1).strip().upper()
            percent_value = float(match.group(2).strip())
            await stop_loss_percent_service.save_or_update(
                StopLossPercentItem(symbol=symbol, value=percent_value)
            )
            await callback_query.message.answer(
                f"ℹ Stop loss for {html.bold(symbol)} at {html.bold(str(percent_value) + '%')} has been successfully stored and it will be applied right now!",
                reply_markup=keyboards_builder.get_home_keyboard(),
            )
        except Exception as e:
            logger.error(f"Error persisting stop loss: {str(e)}")
            await callback_query.message.answer(
                f"⚠️ An error occurred while persisting a stop loss. Please try again later:\n\n{html.code(str(e))}"
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to set the stop loss percent (%).",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
