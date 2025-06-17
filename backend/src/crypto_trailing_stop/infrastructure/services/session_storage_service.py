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

    async def find_fsm_context(self, key: StorageKey) -> FSMContext:
        return FSMContext(
            storage=self._dispacher.storage,
            key=key,
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
