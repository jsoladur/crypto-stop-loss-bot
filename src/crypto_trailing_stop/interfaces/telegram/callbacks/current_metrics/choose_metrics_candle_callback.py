import logging
import re

from aiogram import F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_dispacher
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()


@dp.callback_query(F.data.regexp(r"^choose_metrics_candle\$\$(.+)$"))
async def choose_metrics_candle_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        match = re.match(r"^choose_metrics_candle\$\$(.+)$", callback_query.data)
        symbol = match.group(1)
        await callback_query.message.answer(
            f"ℹ️ Choose a recent {html.bold(symbol)} candlestick to view its metrics.\n"
            + f"⚠️ Please NOTE: {html.bold('The CURRENT candle IS NOT CONFIRMED yet!')}",
            reply_markup=keyboards_builder.get_choose_metrics_candle_keyboard(symbol),
        )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to get current crypto metrics for any symbol.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
