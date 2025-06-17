import logging
from aiogram import html
from aiogram.filters import CommandStart
from aiogram.types import Message

from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.infrastructure.services import SessionStorageService
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

dp = get_dispacher()
session_storage_service = SessionStorageService()
keyboards_builder = KeyboardsBuilder()


@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    # The stage will allow to us to store user data!
    reply_message = f"Hello, {html.bold(message.from_user.full_name)}!"
    is_user_logged = await session_storage_service.is_user_logged(state)
    if is_user_logged:
        keyboard = keyboards_builder.get_home_keyboard()
    else:
        reply_message += "⚠️ Please log in to continue."
        keyboard = keyboards_builder.get_login_keyboard(state)
    await message.answer(reply_message, reply_markup=keyboard)
