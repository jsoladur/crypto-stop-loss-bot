import logging

from crypto_trailing_stop.commons.patterns import SingletonMeta
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService

logger = logging.getLogger(__name__)


class CryptoAnalyticsService(metaclass=SingletonMeta):
    def __init__(self, bit2me_remote_service: Bit2MeRemoteService) -> None:
        self._bit2me_remote_service = bit2me_remote_service

    async def get_tickers_for_favourite_crypto_currencies(self) -> list[Bit2MeTickersDto]:
        async with await self._bit2me_remote_service.get_http_client() as client:
            account_info = await self._bit2me_remote_service.get_account_info(client=client)
            favourite_crypto_currencies = await self._bit2me_remote_service.get_favourite_crypto_currencies(
                client=client
            )
            ret = [
                await self._bit2me_remote_service.get_tickers_by_symbol(
                    symbol=f"{crypto_currency}/{account_info.profile.currency_code}", client=client
                )
                for crypto_currency in favourite_crypto_currencies
            ]
            return ret
