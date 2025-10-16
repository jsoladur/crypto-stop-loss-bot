import logging

from aiogram import Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.interfaces.telegram.internal.home_handler import HomeHandler

logger = logging.getLogger(__name__)

application_container = get_application_container()
dp: Dispatcher = application_container.dispatcher()
home_handler: HomeHandler = application_container().interfaces_container().telegram_container().home_handler()


@dp.callback_query(lambda c: c.data == "go_back_home")
async def go_back_home_callback_handler(callback_query: CallbackQuery, state: FSMContext) -> None:
    await home_handler.handle(callback_query.message, state)
