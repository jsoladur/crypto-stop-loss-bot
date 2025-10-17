from dependency_injector import providers

from crypto_trailing_stop.config.configuration_properties import ConfigurationProperties
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.base import AbstractOperatingExchangeService
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import OperatingExchangeEnum


class OperatingExchangeServiceFactory:
    def __init__(
        self, configuration_properties: ConfigurationProperties, adapters_container: providers.Container
    ) -> None:
        self._configuration_properties = configuration_properties
        self._adapters_container = adapters_container
        self._services_by_exchange: dict[OperatingExchangeEnum, AbstractOperatingExchangeService] = {}
        self._load_services(adapters_container)

    def get_service(self) -> AbstractOperatingExchangeService:
        self._configuration_properties.operating_exchange

    def _load_services(self) -> None:
        for provider in self._adapters_container.traverse(types=[providers.Singleton]):
            dependency_object = provider()
            if isinstance(dependency_object, AbstractOperatingExchangeService):
                exchange_name = dependency_object.get_exchange_name()
                self._services_by_exchange[exchange_name] = dependency_object
