from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from crypto_trailing_stop.config.dependencies import get_dispacher
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.internal.home_handler import HomeHandler
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

dp = get_dispacher()
home_handler = HomeHandler(session_storage_service=SessionStorageService(), keyboards_builder=KeyboardsBuilder())


@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    await home_handler.handle(message, state)
