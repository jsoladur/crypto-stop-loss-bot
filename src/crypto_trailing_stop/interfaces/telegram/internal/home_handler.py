from aiogram import html
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from crypto_trailing_stop.commons.patterns import SingletonMeta
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder


class HomeHandler(metaclass=SingletonMeta):
    def __init__(self, session_storage_service: SessionStorageService, keyboards_builder: KeyboardsBuilder) -> None:
        self._session_storage_service = session_storage_service
        self._keyboards_builder = keyboards_builder

    async def handle(self, message: Message, state: FSMContext) -> None:
        # The stage will allow to us to store user data!
        reply_message = f"Hello, {html.bold(message.from_user.full_name)}!"
        is_user_logged = await self._session_storage_service.is_user_logged(state)
        if is_user_logged:
            keyboard = self._keyboards_builder.get_home_keyboard()
        else:
            reply_message += " ⚠️ Please log in to continue."
            keyboard = self._keyboards_builder.get_login_keyboard(state)
        await message.answer(reply_message, reply_markup=keyboard)
