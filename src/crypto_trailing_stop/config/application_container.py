from dependency_injector import containers, providers

from crypto_trailing_stop.config.configuration_properties import ConfigurationProperties
from crypto_trailing_stop.infrastructure.config.infrastructure_container import InfrastructureContainer
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.config.interfaces_container import InterfacesContainer


class ApplicationContainer(containers.DeclarativeContainer):
    configuration_properties = providers.Singleton(ConfigurationProperties)

    session_storage_service = providers.Singleton(
        SessionStorageService, configuration_properties=configuration_properties
    )

    interfaces_container = providers.Container(
        InterfacesContainer,
        configuration_properties=configuration_properties,
        session_storage_service=session_storage_service,
    )

    infrastructure_container = providers.Container(
        InfrastructureContainer,
        configuration_properties=configuration_properties,
        telegram_service=interfaces_container.telegram_service,
    )
