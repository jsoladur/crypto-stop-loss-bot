import logging
import re

from aiogram import Dispatcher, F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.services.auto_entry_trader_event_handler_service import (
    AutoEntryTraderEventHandlerService,
)
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.exception_utils import format_exception
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

application_container = get_application_container()
dp: Dispatcher = application_container.dispatcher()
session_storage_service: SessionStorageService = application_container.session_storage_service()
keyboards_builder: KeyboardsBuilder = (
    application_container.interfaces_container().telegram_container().keyboards_builder()
)
auto_entry_trader_event_handler_service: AutoEntryTraderEventHandlerService = (
    application_container.infrastructure_container().services_container().auto_entry_trader_event_handler_service()
)


@dp.callback_query(F.data.regexp(r"^trigger_auto_entry_trader\$\$(.+)$"))
async def trigger_auto_entry_trader_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            match = re.match(r"^trigger_auto_entry_trader\$\$(.+)$", callback_query.data)
            symbol = match.group(1)
            await auto_entry_trader_event_handler_service.trigger_immediate_buy_market_signal(symbol)
            await callback_query.message.answer(
                f"ℹ️ Auto-Entry Trader has been successfully triggered for {symbol}. "
                + "You will receive a push notification once the operations are completed.",
                reply_markup=keyboards_builder.get_home_keyboard(),
            )
        except Exception as e:
            logger.error(f"Error triggering Auto-Entry Trader: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                "⚠️ An error occurred while triggering Auto-Entry Trader"
                + f"Please try again later:\n\n{html.code(format_exception(e))}"
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to manual trigger Auto-Entry Trader.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
