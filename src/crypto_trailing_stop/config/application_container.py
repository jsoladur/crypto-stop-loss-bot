import tomllib
from os import getcwd
from pathlib import Path

from dependency_injector import containers, providers

from crypto_trailing_stop.config.configuration_properties import ConfigurationProperties
from crypto_trailing_stop.infrastructure.adapters.config.adapters_container import AdaptersContainer
from crypto_trailing_stop.infrastructure.config.infrastructure_container import InfrastructureContainer
from crypto_trailing_stop.interfaces.config.interfaces_container import InterfacesContainer


class ApplicationContainer(containers.DeclarativeContainer):
    configuration_properties = providers.Singleton(ConfigurationProperties)

    @staticmethod
    def _project_version() -> str:
        pyproject_path = Path(getcwd()) / "pyproject.toml"
        with pyproject_path.open("rb") as f:
            pyproject = tomllib.load(f)
        ret = pyproject["project"]["version"]
        return ret

    application_version: str = providers.Callable(_project_version)

    adapters_container = providers.Container(AdaptersContainer, configuration_properties=configuration_properties)

    interfaces_container = providers.Container(
        InterfacesContainer,
        configuration_properties=configuration_properties,
        operating_exchange_service=adapters_container.operating_exchange_service,
    )
    infrastructure_container = providers.Container(
        InfrastructureContainer,
        configuration_properties=configuration_properties,
        operating_exchange_service=adapters_container.operating_exchange_service,
        ccxt_remote_service=adapters_container.ccxt_remote_service,
        gemini_remote_service=adapters_container.gemini_remote_service,
        telegram_service=interfaces_container.telegram_container.telegram_service,
    )
