from aiogram.filters import CommandStart
from aiogram.types import Message

from crypto_trailing_stop.config import get_dispacher
from aiogram.fsm.context import FSMContext
from crypto_trailing_stop.interfaces.telegram.internal.home_handler import HomeHandler

dp = get_dispacher()
home_handler = HomeHandler()


@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    await home_handler.handle(message, state)
