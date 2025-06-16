from aiogram.fsm.context import FSMContext
from crypto_trailing_stop.infrastructure.services.enums import (
    SessionKeysEnum,
)


class SessionStorageService:
    async def is_user_logged(self, state: FSMContext) -> bool:
        data = await state.get_data()
        return SessionKeysEnum.USER_CONTEXT.value in data
