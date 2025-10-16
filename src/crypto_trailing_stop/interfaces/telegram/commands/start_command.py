from aiogram import Dispatcher
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.telegram.internal.home_handler import HomeHandler
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder

application_container = get_application_container()
dp: Dispatcher = application_container.dispatcher()
session_storage_service: SessionStorageService = application_container.session_storage_service()
keyboards_builder: KeyboardsBuilder = (
    application_container.interfaces_container().telegram_container().keyboards_builder()
)
home_handler: HomeHandler = application_container.interfaces_container().telegram_container().home_handler()


@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    await home_handler.handle(message, state)
