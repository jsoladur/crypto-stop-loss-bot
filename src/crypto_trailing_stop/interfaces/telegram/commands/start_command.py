from aiogram.filters import CommandStart
from aiogram.types import Message

from crypto_trailing_stop.config import get_dispacher
from aiogram.fsm.context import FSMContext
from crypto_trailing_stop.interfaces.telegram.internal.home_handler import HomeHandler
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.infrastructure.services import SessionStorageService

dp = get_dispacher()
home_handler = HomeHandler(
    session_storage_service=SessionStorageService(),
    keyboards_builder=KeyboardsBuilder(),
)


@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    await home_handler.handle(message, state)
