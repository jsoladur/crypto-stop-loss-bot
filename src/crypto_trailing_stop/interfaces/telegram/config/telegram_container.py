from dependency_injector import containers, providers

from crypto_trailing_stop.interfaces.telegram.keyboards_builder import KeyboardsBuilder
from crypto_trailing_stop.interfaces.telegram.messages_formatter import MessagesFormatter
from crypto_trailing_stop.interfaces.telegram.services.telegram_service import TelegramService


class TelegramContainer(containers.DeclarativeContainer):
    configuration_properties = providers.Dependency()
    session_storage_service = providers.Dependency()

    keyboards_builder = providers.Singleton(KeyboardsBuilder, configuration_properties=configuration_properties)
    messages_formatter = providers.Singleton(MessagesFormatter)

    telegram_service = providers.Singleton(
        TelegramService, keyboards_builder=keyboards_builder, session_storage_service=session_storage_service
    )
