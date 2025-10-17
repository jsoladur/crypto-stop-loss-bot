from dependency_injector import containers, providers

from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.gemini_remote_service import GeminiRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.factory import (
    OperatingExchangeServiceFactory,
)
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.impl.bit2me_operating_exchange_service import (  # noqa: E501
    Bit2MeOperatingExchangeService,
)
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.impl.mexc_operating_exchange_service import (  # noqa: E501
    MEXCOperatingExchangeService,
)


class AdaptersContainer(containers.DeclarativeContainer):
    __self__ = providers.Self()

    configuration_properties = providers.Dependency()

    bit2me_remote_service = providers.Singleton(Bit2MeRemoteService, configuration_properties=configuration_properties)
    ccxt_remote_service = providers.Singleton(CcxtRemoteService)
    gemini_remote_service = providers.Singleton(GeminiRemoteService, configuration_properties=configuration_properties)

    bit2me_operating_exchange_service = providers.Singleton(
        Bit2MeOperatingExchangeService, bit2me_remote_service=bit2me_remote_service
    )
    mexc_operating_exchange_service = providers.Singleton(MEXCOperatingExchangeService)

    operating_exchange_service_factory = providers.Singleton(
        OperatingExchangeServiceFactory, configuration_properties=configuration_properties, adapters_container=__self__
    )
