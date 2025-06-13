import logging
from aiogram import html
from aiogram.filters import CommandStart
from aiogram.types import Message
from crypto_trailing_stop.config import get_dispacher
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)
dp = get_dispacher()


@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    # The stage will allow to us to store user data!
    logger.info(repr(state))
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!")
