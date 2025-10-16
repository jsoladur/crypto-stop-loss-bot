from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram_dialog import setup_dialogs
from dependency_injector import containers, providers

from crypto_trailing_stop.config.configuration_properties import ConfigurationProperties
from crypto_trailing_stop.infrastructure.config.infrastructure_container import InfrastructureContainer
from crypto_trailing_stop.infrastructure.services.session_storage_service import SessionStorageService
from crypto_trailing_stop.interfaces.config.interfaces_container import InterfacesContainer


class ApplicationContainer(containers.DeclarativeContainer):
    configuration_properties = providers.Singleton(ConfigurationProperties)

    @staticmethod
    def _dispacher() -> Dispatcher:
        dispacher = Dispatcher(storage=MemoryStorage())
        setup_dialogs(dispacher)
        return dispacher

    dispatcher = providers.Singleton(_dispacher)

    session_storage_service = providers.Singleton(
        SessionStorageService, configuration_properties=configuration_properties, dispatcher=dispatcher
    )

    interfaces_container = providers.Container(
        InterfacesContainer,
        configuration_properties=configuration_properties,
        session_storage_service=session_storage_service,
    )

    infrastructure_container = providers.Container(
        InfrastructureContainer,
        configuration_properties=configuration_properties,
        telegram_service=interfaces_container.telegram_container.telegram_service,
    )
