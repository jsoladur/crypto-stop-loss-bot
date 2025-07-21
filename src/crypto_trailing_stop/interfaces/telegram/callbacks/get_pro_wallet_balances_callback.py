import logging
from html import escape as html_escape

from aiogram import html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.interfaces.telegram.messages_formatter import MessagesFormatter

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()
messages_formatter = MessagesFormatter()
bit2me_remote_service = Bit2MeRemoteService()


@dp.callback_query(lambda c: c.data == "get_pro_wallet_balances")
async def get_pro_wallet_balances_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            async with await bit2me_remote_service.get_http_client() as client:
                account_info = await bit2me_remote_service.get_account_info(client=client)
                trading_wallet_balances = await bit2me_remote_service.get_trading_wallet_balances(client=client)
            message = messages_formatter.format_trading_wallet_balances(account_info, trading_wallet_balances)
            await callback_query.message.answer(text=message)
        except Exception as e:
            logger.error(f"Error fetching get Bit2Me Pro Wallet balances: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                "⚠️ An error occurred while fetching Bit2Me Pro Wallet balances. "
                + f"Please try again later:\n\n{html.code(html_escape(str(e)))}"
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to get the current Bit2Me Pro Wallet balances!",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
