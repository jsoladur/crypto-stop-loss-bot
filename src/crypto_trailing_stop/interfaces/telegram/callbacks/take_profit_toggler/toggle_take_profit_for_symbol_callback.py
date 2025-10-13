import logging
import re

from aiogram import F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.favourite_crypto_currency_service import (
    FavouriteCryptoCurrencyService,
)
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.exception_utils import format_exception
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
buy_sell_signals_config_service = BuySellSignalsConfigService(
    favourite_crypto_currency_service=FavouriteCryptoCurrencyService(bit2me_remote_service=Bit2MeRemoteService())
)

REGEX = r"^take_profit_toggler\$\$(.+)$"


@dp.callback_query(F.data.regexp(REGEX))
async def toggle_take_profit_for_symbol_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            match = re.match(REGEX, callback_query.data)
            symbol = match.group(1)
            item = await buy_sell_signals_config_service.toggle_enable_exit_on_take_profit_by_symbol(symbol)
            await callback_query.message.answer(
                f"ℹ️ Take-Profit for '{html.bold(symbol)}'"
                + f" has been {('🟢' + html.bold(' ENABLED')) if item.enable_exit_on_take_profit else ('🟥' + html.bold(' DISABLED'))}!",  # noqa: E501
                reply_markup=keyboards_builder.get_home_keyboard(),
            )
        except Exception as e:
            logger.error(f"Error trying to toggle push notifications for this chat: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while toggling push notifications. Please try again later:\n\n{html.code(format_exception(e))}"  # noqa: E501
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to operate with Global Flags.", reply_markup=keyboards_builder.get_login_keyboard(state)
        )
