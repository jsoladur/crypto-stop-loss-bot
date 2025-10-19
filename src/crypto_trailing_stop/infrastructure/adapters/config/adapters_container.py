from dependency_injector import containers, providers

from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.ccxt_remote_service import CcxtRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.gemini_remote_service import GeminiRemoteService
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums.operating_exchange_enum import (
    OperatingExchangeEnum,
)
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.factory import (
    OperatingExchangeServiceFactory,
)
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.impl.bit2me_operating_exchange_service import (  # noqa: E501
    Bit2MeOperatingExchangeService,
)

# from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.impl.mexc_operating_exchange_service import (  # noqa: E501
#     MEXCOperatingExchangeService,
# )


class AdaptersContainer(containers.DeclarativeContainer):
    __self__ = providers.Self()

    configuration_properties = providers.Dependency()

    # Bit2Me remote service is considered private and should not be accessed directly, only in this container
    _bit2me_remote_service = providers.Singleton(Bit2MeRemoteService, configuration_properties=configuration_properties)
    _bit2me_operating_exchange_service = providers.Singleton(
        Bit2MeOperatingExchangeService, bit2me_remote_service=_bit2me_remote_service
    )

    # _mexc_operating_exchange_service = providers.Singleton(MEXCOperatingExchangeService)

    ccxt_remote_service = providers.Singleton(CcxtRemoteService)
    gemini_remote_service = providers.Singleton(GeminiRemoteService, configuration_properties=configuration_properties)

    operating_exchange_service_factory = providers.Singleton(
        OperatingExchangeServiceFactory, configuration_properties=configuration_properties, adapters_container=__self__
    )

    operating_exchange_service = providers.Selector(
        configuration_properties.provided.operating_exchange,
        **{
            # TODO: Enable when MEXC implementation is ready
            # OperatingExchangeEnum.MEXC: _mexc_operating_exchange_service,
            OperatingExchangeEnum.BIT2ME: _bit2me_operating_exchange_service
        },
    )
