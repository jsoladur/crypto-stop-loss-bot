from dependency_injector import containers, providers

from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.gemini_remote_service import GeminiRemoteService


class AdaptersContainer(containers.DeclarativeContainer):
    configuration_properties = providers.Dependency()

    bit2me_remote_service = providers.Singleton(Bit2MeRemoteService, configuration_properties=configuration_properties)
    ccxt_remote_service = providers.Singleton(CcxtRemoteService)
    gemini_remote_service = providers.Singleton(GeminiRemoteService, configuration_properties=configuration_properties)
