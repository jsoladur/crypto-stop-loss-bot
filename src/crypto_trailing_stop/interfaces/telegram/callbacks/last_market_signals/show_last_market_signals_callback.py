import logging
import re

from aiogram import Dispatcher, F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange import AbstractOperatingExchangeService
from crypto_trailing_stop.infrastructure.services.market_signal_service import MarketSignalService
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
operating_exchange_service: AbstractOperatingExchangeService = (
    application_container.infrastructure_container().adapters_container().bit2me_remote_service()
)
market_signal_service: MarketSignalService = (
    application_container.infrastructure_container().services_container().market_signal_service()
)


@dp.callback_query(F.data.regexp(r"^show_last_market_signals\$\$(.+)$"))
async def show_last_market_signals_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            match = re.match(r"^show_last_market_signals\$\$(.+)$", callback_query.data)
            symbol = match.group(1)
            market_signals = await market_signal_service.find_by_symbol(symbol)
            trading_market_config = await operating_exchange_service.get_trading_market_config_by_symbol(symbol)
            message = messages_formatter.format_market_signals_message(symbol, trading_market_config, market_signals)
            await callback_query.message.answer(message, reply_markup=keyboards_builder.get_go_back_home_keyboard())
        except Exception as e:
            logger.error(f"Error fetching last market signals: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                "⚠️ An error occurred while fetching last market signals. "
                + f"Please try again later:\n\n{html.code(format_exception(e))}"
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to fetch the last market signals.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
