from crypto_trailing_stop.config import get_configuration_properties
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.base import AbstractOperatingExchangeService
from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.enums import OperatingExchangeEnum


class OperatingExchangeServiceFactory:
    _service: AbstractOperatingExchangeService = None

    @classmethod
    def get_service(cls) -> AbstractOperatingExchangeService:
        if cls._service is None:
            configuration_properties = get_configuration_properties()
            cls._service = cls._create(configuration_properties.operating_exchange)
        return cls._service

    @staticmethod
    def _create(exchange_name: OperatingExchangeEnum) -> AbstractOperatingExchangeService:
        match exchange_name:
            case OperatingExchangeEnum.BIT2ME:
                from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import (
                    Bit2MeRemoteService,
                )
                from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange.impl.bit2me_operating_exchange_service import (  # noqa: E501
                    Bit2MeOperatingExchangeService,
                )

                return Bit2MeOperatingExchangeService(bit2me_remote_service=Bit2MeRemoteService())
            case _:
                raise ValueError(f"Unsupported exchange: {exchange_name}")
