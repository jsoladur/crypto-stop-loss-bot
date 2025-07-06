import logging

from aiogram import html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.services.crypto_analytics_service import CryptoAnalyticsService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()

crypto_analytics_service = CryptoAnalyticsService(
    bit2me_remote_service=Bit2MeRemoteService(), ccxt_remote_service=CcxtRemoteService()
)


@dp.callback_query(lambda c: c.data == "get_current_prices")
async def get_current_prices_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            tickers_list = await crypto_analytics_service.get_favourite_tickers()
            message_lines = ["===========================", "💵 CURRENT PRICES 💵", "==========================="]
            for tickers in tickers_list:
                crypto_currency, fiat_currency = tickers.symbol.split("/")
                message_lines.append(
                    f"🔥 {html.bold(crypto_currency.upper())} 💰 {html.bold(str(tickers.close) + ' ' + fiat_currency)}"
                )
            await callback_query.message.answer(text="\n".join(message_lines))
        except Exception as e:
            logger.error(f"Error fetching get current crypto currency prices: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                "⚠️ An error occurred while fetching current crypto currency prices. "
                + f"Please try again later:\n\n{html.code(str(e))}"
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to get the current crypto currency prices!",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
