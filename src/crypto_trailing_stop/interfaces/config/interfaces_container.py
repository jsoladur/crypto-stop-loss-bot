from dependency_injector import containers, providers

from crypto_trailing_stop.interfaces.controllers.config.controllers_config import ControllersContainer
from crypto_trailing_stop.interfaces.telegram.config.telegram_container import TelegramContainer


class InterfacesContainer(containers.DeclarativeContainer):
    configuration_properties = providers.Dependency()
    operating_exchange_service = providers.Dependency()

    telegram_container = providers.Container(
        TelegramContainer,
        configuration_properties=configuration_properties,
        operating_exchange_service=operating_exchange_service,
    )

    controllers_container = providers.Container(ControllersContainer, configuration_properties=configuration_properties)
