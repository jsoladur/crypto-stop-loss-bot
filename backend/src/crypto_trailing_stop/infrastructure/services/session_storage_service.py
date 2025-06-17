from aiogram.fsm.context import FSMContext
from crypto_trailing_stop.infrastructure.services.enums import (
    SessionKeysEnum,
)
from crypto_trailing_stop.config import get_dispacher
from aiogram.fsm.storage.base import StorageKey
from typing import Any


class SessionStorageService:
    def __init__(self):
        self._dispacher = get_dispacher()

    async def get_or_create_fsm_context(
        self, *, bot_id: int, chat_id: int, user_id: int
    ) -> FSMContext:
        return FSMContext(
            storage=self._dispacher.storage,
            key=StorageKey(
                bot_id=int(bot_id),
                chat_id=int(chat_id),
                user_id=int(user_id),
            ),
        )

    async def is_user_logged(self, state: FSMContext) -> bool:
        data = await state.get_data()
        return SessionKeysEnum.USER_CONTEXT.value in data

    async def set_user_logged(
        self, state: FSMContext, userinfo: dict[str, Any]
    ) -> None:
        data = await state.get_data()
        data[SessionKeysEnum.USER_CONTEXT.value] = userinfo
        await state.set_data(data)

    async def perform_logout(self, state: FSMContext) -> bool:
        data = await state.get_data()
        if SessionKeysEnum.USER_CONTEXT.value in data:
            await state.clear()
