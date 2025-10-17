from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dependency_injector import containers, providers

from crypto_trailing_stop.config.configuration_properties import ConfigurationProperties
from crypto_trailing_stop.interfaces.telegram.internal.home_handler import HomeHandler
from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.interfaces.telegram.messages_formatter import MessagesFormatter
from crypto_trailing_stop.interfaces.telegram.services.telegram_service import TelegramService


class TelegramContainer(containers.DeclarativeContainer):
    configuration_properties = providers.Dependency()
    session_storage_service = providers.Dependency()

    @staticmethod
    def _telegram_bot(configuration_properties: ConfigurationProperties) -> Bot:
        bot = Bot(
            token=configuration_properties.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        return bot

    telegram_bot = providers.Singleton(_telegram_bot, configuration_properties=configuration_properties)
    keyboards_builder = providers.Singleton(KeyboardsBuilder, configuration_properties=configuration_properties)
    messages_formatter = providers.Singleton(MessagesFormatter)

    home_handler = providers.Singleton(
        HomeHandler, session_storage_service=session_storage_service, keyboards_builder=keyboards_builder
    )

    telegram_service = providers.Singleton(
        TelegramService,
        telegram_bot=telegram_bot,
        keyboards_builder=keyboards_builder,
        session_storage_service=session_storage_service,
    )
