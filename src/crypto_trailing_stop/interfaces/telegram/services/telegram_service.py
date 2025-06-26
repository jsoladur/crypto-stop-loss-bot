from crypto_trailing_stop.config import get_telegram_bot
from crypto_trailing_stop.interfaces.dtos.login_dto import LoginDto
from crypto_trailing_stop.infrastructure.services import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from aiogram.types import ReplyMarkupUnion
from typing import Any


class TelegramService:
    def __init__(
        self,
        session_storage_service: SessionStorageService,
        keyboards_builder: KeyboardsBuilder,
    ) -> None:
        self._telegram_bot = get_telegram_bot()
        self._session_storage_service = session_storage_service
        self._keyboards_builder = keyboards_builder

    async def perform_successful_login(
        self, login: LoginDto, userinfo: dict[str, Any]
    ) -> None:
        """Sets the user as logged in by storing their information in the session."""
        state = await self._session_storage_service.get_or_create_fsm_context(
            bot_id=login.tg_bot_id,
            chat_id=login.tg_chat_id,
            user_id=login.tg_user_id,
        )
        if not state:
            raise ValueError(
                f"State not found for chat_id={login.tg_chat_id} and user_id={login.tg_user_id}"
            )
        await self._session_storage_service.set_user_logged(
            state=state, userinfo=userinfo
        )
        await self.send_message(
            chat_id=login.tg_chat_id,
            text="You have successfully logged in to Crypto Trailing Stop.",
            reply_markup=self._keyboards_builder.get_home_keyboard(),
        )

    async def send_message(
        self,
        chat_id: str | None,
        text: str,
        *,
        reply_to_message_id: int | None = None,
        reply_markup: ReplyMarkupUnion | None = None,
    ) -> None:
        """Sends a message to a specified Telegram chat."""
        await self._telegram_bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_to_message_id=reply_to_message_id,
            reply_markup=reply_markup,
        )
