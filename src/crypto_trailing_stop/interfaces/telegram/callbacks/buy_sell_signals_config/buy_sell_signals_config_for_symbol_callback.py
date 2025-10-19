import logging
import re

from aiogram import Dispatcher, F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.exception_utils import format_exception
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.interfaces.telegram.messages_formatter import MessagesFormatter

logger = logging.getLogger(__name__)

application_container = get_application_container()
dp: Dispatcher = application_container.interfaces_container().telegram_container().dispatcher()
session_storage_service: SessionStorageService = (
    application_container.interfaces_container().telegram_container().session_storage_service()
)
keyboards_builder: KeyboardsBuilder = (
    application_container.interfaces_container().telegram_container().keyboards_builder()
)
messages_formatter: MessagesFormatter = (
    application_container.interfaces_container().telegram_container().messages_formatter()
)
buy_sell_signals_config_service: BuySellSignalsConfigService = (
    application_container.infrastructure_container().services_container().buy_sell_signals_config_service()
)


@dp.callback_query(F.data.regexp(r"^set_buy_sell_signals_config\$\$(.+)$"))
async def auto_entry_trader_config_for_symbol_callback_handler(
    callback_query: CallbackQuery, state: FSMContext
) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            match = re.match(r"^set_buy_sell_signals_config\$\$(.+)$", callback_query.data)
            symbol = match.group(1)
            item = await buy_sell_signals_config_service.find_by_symbol(symbol)
            buy_sell_signals_config_formatted = messages_formatter.format_buy_sell_signals_config_message(item)
            message = (
                f"⚡ Buy-Sell Signals config for {html.bold(symbol)} ⚡\n\n"
                + buy_sell_signals_config_formatted
                + "ℹ️️ Would you like to modify these parameters?"
            )
            await callback_query.message.answer(
                message,
                reply_markup=keyboards_builder.get_yes_no_keyboard(
                    yes_button_callback_data=f"persist_buy_sell_signals_config$${symbol}"
                ),
            )
        except Exception as e:
            logger.error(f"Error retrieving buy/sell signals configuration: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while retrieving buy/sell signals configuration. Please try again later:\n\n{html.code(format_exception(e))}"  # noqa: E501
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to set buy/sell signals configuration.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
