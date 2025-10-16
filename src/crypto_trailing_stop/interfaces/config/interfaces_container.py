from dependency_injector import containers, providers

from crypto_trailing_stop.interfaces.controllers.config.controllers_config import ControllersContainer
from crypto_trailing_stop.interfaces.telegram.config.telegram_container import TelegramContainer


class InterfacesContainer(containers.DeclarativeContainer):
    configuration_properties = providers.Dependency()
    session_storage_service = providers.Dependency()

    telegram_container = providers.Container(
        TelegramContainer,
        configuration_properties=configuration_properties,
        session_storage_service=session_storage_service,
    )

    controllers_container = providers.Container(ControllersContainer, configuration_properties=configuration_properties)
