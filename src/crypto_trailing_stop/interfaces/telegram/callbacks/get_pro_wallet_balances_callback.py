import logging

from aiogram import Dispatcher, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.services.global_summary_service import GlobalSummaryService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.exception_utils import format_exception
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.interfaces.telegram.messages_formatter import MessagesFormatter

logger = logging.getLogger(__name__)

application_container = get_application_container()
dp: Dispatcher = application_container.dispatcher()
session_storage_service: SessionStorageService = application_container.session_storage_service()
keyboards_builder: KeyboardsBuilder = (
    application_container.interfaces_container().telegram_container().keyboards_builder()
)
messages_formatter: MessagesFormatter = (
    application_container.interfaces_container().telegram_container().messages_formatter()
)
bit2me_remote_service: Bit2MeRemoteService = (
    application_container.infrastructure_container().adapters_container().bit2me_remote_service()
)
global_summary_service: GlobalSummaryService = (
    application_container.infrastructure_container().services_container().global_summary_service()
)


@dp.callback_query(lambda c: c.data == "get_pro_wallet_balances")
async def get_pro_wallet_balances_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            async with await bit2me_remote_service.get_http_client() as client:
                account_info = await bit2me_remote_service.get_account_info(client=client)
                total_portfolio_fiat_amount = await global_summary_service.calculate_portfolio_total_fiat_amount(
                    account_info.profile.currency_code, client=client
                )
                trading_wallet_balances = await bit2me_remote_service.get_trading_wallet_balances(client=client)
            message = messages_formatter.format_trading_wallet_balances(
                account_info, trading_wallet_balances, total_portfolio_fiat_amount
            )
            await callback_query.message.answer(text=message)
        except Exception as e:
            logger.error(f"Error fetching get Bit2Me Pro Wallet balances: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                "⚠️ An error occurred while fetching Bit2Me Pro Wallet balances. "
                + f"Please try again later:\n\n{html.code(format_exception(e))}"
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to get the current Bit2Me Pro Wallet balances!",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
