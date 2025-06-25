from aiogram import html
from aiogram.types import Message

from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.infrastructure.services import SessionStorageService
from aiogram.fsm.context import FSMContext


class HomeHandler:
    def __init__(self):
        self._session_storage_service = SessionStorageService()
        self._keyboards_builder = KeyboardsBuilder()

    async def handle(self, message: Message, state: FSMContext) -> None:
        # The stage will allow to us to store user data!
        reply_message = f"Hello, {html.bold(message.from_user.full_name)}!"
        # FIXME: Uncomment this!
        # is_user_logged = await self._session_storage_service.is_user_logged(state)
        is_user_logged = True
        if is_user_logged:
            keyboard = self._keyboards_builder.get_home_keyboard()
        else:
            reply_message += " ⚠️ Please log in to continue."
            keyboard = self._keyboards_builder.get_login_keyboard(state)
        await message.answer(reply_message, reply_markup=keyboard)
