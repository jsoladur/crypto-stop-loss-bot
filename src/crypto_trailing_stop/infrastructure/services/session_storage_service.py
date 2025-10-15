from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

from crypto_trailing_stop.config.configuration_properties import ConfigurationProperties
from crypto_trailing_stop.infrastructure.services.enums import SessionKeysEnum


class SessionStorageService:
    def __init__(self, configuration_properties: ConfigurationProperties):
        # FIXME: Review this circular import!
        from crypto_trailing_stop.config.dependencies import get_dispacher

        self._configuration_properties = configuration_properties
        self._dispacher = get_dispacher()
        self._in_memory_storage_by_chat_id: dict[str, dict[str, Any]] = {}

    async def get_or_create_fsm_context(self, *, bot_id: int, chat_id: int, user_id: int) -> FSMContext:
        return FSMContext(
            storage=self._dispacher.storage,
            key=StorageKey(bot_id=int(bot_id), chat_id=int(chat_id), user_id=int(user_id)),
        )

    async def is_user_logged(self, state: FSMContext) -> bool:
        if not self._configuration_properties.login_enabled:  # pragma: no cover
            ret = True
        else:
            data = await state.get_data()
            ret = SessionKeysEnum.USER_CONTEXT.value in data
        return ret

    async def set_user_logged(self, state: FSMContext, userinfo: dict[str, Any]) -> None:
        data = await state.get_data()
        data[SessionKeysEnum.USER_CONTEXT.value] = userinfo
        await state.set_data(data)

    async def get_buy_sell_signals_symbol_form(self, chat_id: int) -> str:
        data = self._in_memory_storage_by_chat_id.setdefault(chat_id, {})
        if SessionKeysEnum.BUY_SELL_SIGNALS_SYMBOL_FORM.value not in data:
            return ValueError("Missing buy/sell signals symbol form")
        symbol = data.pop(SessionKeysEnum.BUY_SELL_SIGNALS_SYMBOL_FORM.value)
        return symbol

    async def set_buy_sell_signals_symbol_form(self, state: FSMContext, symbol: str) -> None:
        data = self._in_memory_storage_by_chat_id.setdefault(state.key.chat_id, {})
        data[SessionKeysEnum.BUY_SELL_SIGNALS_SYMBOL_FORM.value] = symbol

    async def perform_logout(self, state: FSMContext) -> bool:
        data = await state.get_data()
        if SessionKeysEnum.USER_CONTEXT.value in data:
            await state.clear()
