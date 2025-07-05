import logging

from httpx import AsyncClient

from crypto_trailing_stop.commons.patterns import SingletonMeta
from crypto_trailing_stop.infrastructure.adapters.dtos.bit2me_tickers_dto import Bit2MeTickersDto
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService

logger = logging.getLogger(__name__)


class CryptoAnalyticsService(metaclass=SingletonMeta):
    def __init__(self, bit2me_remote_service: Bit2MeRemoteService) -> None:
        self._bit2me_remote_service = bit2me_remote_service

    async def get_favourite_tickers(self) -> list[Bit2MeTickersDto]:
        async with await self._bit2me_remote_service.get_http_client() as client:
            favourite_symbols = await self.get_favourite_symbols(client=client)
            ret = [
                await self._bit2me_remote_service.get_tickers_by_symbol(symbol=symbol, client=client)
                for symbol in favourite_symbols
            ]
            return ret

    async def get_favourite_symbols(self, *, client: AsyncClient | None = None) -> list[str]:
        if client:
            ret = await self._internal_get_favourite_symbols(client=client)
        else:
            async with await self._bit2me_remote_service.get_http_client() as client:
                ret = await self._internal_get_favourite_symbols(client=client)
        return ret

    async def _internal_get_favourite_symbols(self, *, client: AsyncClient) -> list[str]:
        favourite_crypto_currencies = await self._bit2me_remote_service.get_favourite_crypto_currencies(client=client)
        bit2me_account_info = await self._bit2me_remote_service.get_account_info(client=client)
        symbols = [
            f"{crypto_currency}/{bit2me_account_info.profile.currency_code}"
            for crypto_currency in favourite_crypto_currencies
        ]
        return symbols
