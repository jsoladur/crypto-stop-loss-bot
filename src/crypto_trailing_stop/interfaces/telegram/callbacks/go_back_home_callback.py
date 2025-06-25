import logging
from aiogram.types import CallbackQuery
from crypto_trailing_stop.config import get_dispacher
from crypto_trailing_stop.interfaces.telegram.internal.home_handler import HomeHandler
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

dp = get_dispacher()
home_handler = HomeHandler()


@dp.callback_query(lambda c: c.data == "go_back_home")
async def go_back_home_callback_handler(
    callback_query: CallbackQuery, state: FSMContext
) -> None:
    await home_handler.handle(callback_query.message, state)
