import logging
import re

from aiogram import Dispatcher, F, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
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
                yes_button_callback_data=f"perform_remove_favourite_currency$${currency}"
            ),
        )
    else:
        await callback_query.message.answer(
            "⚠️ Please log in to operate with favourites crypto currencies.",
            reply_markup=keyboards_builder.get_login_keyboard(state),
        )
