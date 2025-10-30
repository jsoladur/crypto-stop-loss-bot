import logging
import re

from aiogram import Dispatcher, F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.infrastructure.services.trade_now_hints_service import TradeNowHintsService
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
trade_now_hints_service: TradeNowHintsService = (
    application_container.infrastructure_container().services_container().trade_now_hints_service()
)

REGEX = r"^trade_now_result\$\$(.+?)\$\$(.+)$"


@dp.callback_query(F.data.regexp(REGEX))
async def trade_now_result_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        try:
            match = re.match(REGEX, callback_query.data)
            symbol = match.group(1).strip().upper()
            leverage_value = int(match.group(2).strip())
            item = await trade_now_hints_service.get_trade_now_hints(symbol, leverage_value)
            message = messages_formatter.format_trade_now_hints(item)
            await callback_query.message.answer(message, reply_markup=keyboards_builder.get_go_back_home_keyboard())
        except Exception as e:
            logger.error(f"Error calculating trade now hints: {str(e)}", exc_info=True)
            await callback_query.message.answer(
                f"⚠️ An error occurred while calculating trade now hints. Please try again later:\n\n{html.code(format_exception(e))}"  # noqa: E501
            )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to use trade now hints and leverage features.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
