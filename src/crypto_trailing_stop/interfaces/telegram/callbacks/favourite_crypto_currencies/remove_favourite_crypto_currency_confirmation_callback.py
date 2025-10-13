import logging
import re

from aiogram import F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()

REGEX = r"^remove_favourite_crypto_currency\$\$(.+)$"


@dp.callback_query(F.data.regexp(REGEX))
async def remove_favourite_crypto_currency_confirmation_handler(
    callback_query: CallbackQuery, state: FSMContext
) -> None:
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        match = re.match(REGEX, callback_query.data)
        currency = match.group(1)
        await callback_query.message.answer(
            f"⚠️ Are you sure you want to remove {html.bold(currency)} from your favourite crypto currencies?",
            reply_markup=keyboards_builder.get_yes_no_keyboard(
                yes_button_callback_data=f"perform_remove_favourite_currency$${currency}",
                no_button_callback_data="favourite_crypto_currencies_home",
            ),
        )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to operate with favourites crypto currencies.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
