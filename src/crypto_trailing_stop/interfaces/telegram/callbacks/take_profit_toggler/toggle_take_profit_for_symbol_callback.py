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

logger = logging.getLogger(__name__)

application_container = get_application_container()
dp: Dispatcher = application_container.interfaces_container().telegram_container().dispatcher()
session_storage_service: SessionStorageService = (
    application_container.interfaces_container().telegram_container().session_storage_service()
)
keyboards_builder: KeyboardsBuilder = (
    application_container.interfaces_container().telegram_container().keyboards_builder()
)
buy_sell_signals_config_service: BuySellSignalsConfigService = (
    application_container.infrastructure_container().services_container().buy_sell_signals_config_service()
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
