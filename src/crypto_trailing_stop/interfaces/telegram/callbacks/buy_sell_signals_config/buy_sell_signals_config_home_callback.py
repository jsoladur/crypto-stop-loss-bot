import logging
from html import escape as html_escape

from aiogram import html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
buy_sell_signals_config_service = BuySellSignalsConfigService(bit2me_remote_service=Bit2MeRemoteService())


@dp.callback_query(lambda c: c.data == "buy_sell_config_home")
async def auto_entry_trader_config_home_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            items = await buy_sell_signals_config_service.find_all()
            await callback_query.message.answer(
                "ℹ️ Click into a symbol for setting up Buy/Sell signals configuration.",
                reply_markup=keyboards_builder.get_buy_sell_signals_config_keyboard(items),
            )
        except Exception as e:
            logger.error(f"Error retrieving buy/sell signals configuration: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while retrieving buy/sell signals configuration. Please try again later:\n\n{html.code(html_escape(str(e)))}"  # noqa: E501
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to operate with buy/sell signals configuration.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
