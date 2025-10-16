import logging

from aiogram import Dispatcher, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.services.buy_sell_signals_config_service import BuySellSignalsConfigService
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
buy_sell_signals_config_service: BuySellSignalsConfigService = (
    application_container.infrastructure_container().services_container().buy_sell_signals_config_service()
)


@dp.callback_query(lambda c: c.data == "take_profit_toggler_home")
async def take_profit_toggler_home_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            items = await buy_sell_signals_config_service.find_all()
            await callback_query.message.answer(
                "ℹ️ Click into a symbol for toggling any Take-Profit.",
                reply_markup=keyboards_builder.get_take_profit_toggler_home_keyboard(items),
            )
        except Exception as e:
            logger.error(f"Error retrieving buy/sell signals configuration: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while retrieving buy/sell signals configuration. Please try again later:\n\n{html.code(format_exception(e))}"  # noqa: E501
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to operate with the Take-Profit toggler.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
