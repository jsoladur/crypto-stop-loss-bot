import logging
import re

from aiogram import Dispatcher, F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange import AbstractOperatingExchangeService
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

application_container = get_application_container()
dp: Dispatcher = application_container.dispatcher()
session_storage_service: SessionStorageService = application_container.session_storage_service()
keyboards_builder: KeyboardsBuilder = (
    application_container.interfaces_container().telegram_container().keyboards_builder()
)
operating_exchange_service: AbstractOperatingExchangeService = (
    application_container.infrastructure_container().adapters_container().operating_exchange_service()
)

REGEX = r"^immediate_sell_order\$\$(.+)\$\$(.+)$"


@dp.callback_query(F.data.regexp(REGEX))
async def immediate_sell_order_confirmation_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        match = re.match(REGEX, callback_query.data)
        sell_order_id = match.group(1)
        sell_percent = float(match.group(2))
        sell_order = await operating_exchange_service.get_order_by_id(sell_order_id)
        crypto_currency, *_ = sell_order.symbol.split("/")
        formatted_order_ammount = html.bold(f"{sell_order.order_amount} {crypto_currency}")
        await callback_query.message.answer(
            f"🛑 CONFIRM ACTION: IMMEDIATE SELL LIMIT ORDER OF {sell_percent}% FOR {formatted_order_ammount}. "
            + "This operation CANNOT be undone."
            + "\nAre you SURE you want to PROCEED?",
            reply_markup=keyboards_builder.get_yes_no_keyboard(
                yes_button_callback_data=f"trigger_sell_now$${sell_order_id}$${sell_percent}"
            ),
        )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to manual trigger Sell Limit Order.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
