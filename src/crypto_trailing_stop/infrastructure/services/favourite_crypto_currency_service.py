import logging

from crypto_trailing_stop.commons.patterns import SingletonMeta
from crypto_trailing_stop.infrastructure.adapters.remote.bit2me_remote_service import Bit2MeRemoteService
from crypto_trailing_stop.infrastructure.database.models.favourite_crypto_currency import FavouriteCryptoCurrency

logger = logging.getLogger(__name__)


class FavouriteCryptoCurrencyService(metaclass=SingletonMeta):
    def __init__(self, bit2me_remote_service: Bit2MeRemoteService) -> None:
        self._bit2me_remote_service = bit2me_remote_service

    async def find_all(self) -> list[str]:
        favourite_crypto_currencies = await FavouriteCryptoCurrency.objects()
        database_favourites = {
            favourite_crypto_currency.currency for favourite_crypto_currency in favourite_crypto_currencies
        }
        operating_exchange_favourites = await self._bit2me_remote_service.get_favourite_crypto_currencies()
        for exchange_favourite in operating_exchange_favourites:
            if exchange_favourite not in database_favourites:
                logger.warning(
                    f"Favourite crypto currency {exchange_favourite} is not in the database, adding it automatically"
                )
                await self.add(exchange_favourite, remote=False)
        all_favourites = database_favourites.union(operating_exchange_favourites)
        ret = sorted([favourite.upper() for favourite in all_favourites])
        return ret

    async def add(self, currency: str, *, remote: bool = True) -> None:
        currency = currency.upper()
        favourite_crypto_currency = (
            await FavouriteCryptoCurrency.objects().where(FavouriteCryptoCurrency.currency == currency).first()
        )
        if not favourite_crypto_currency:
            if remote:
                await self._bit2me_remote_service.add_favourite_crypto_currency(currency)
            favourite_crypto_currency = FavouriteCryptoCurrency(currency=currency)
            await favourite_crypto_currency.save()
            logger.info(f"Added {currency} to favourite crypto currencies")

    async def remove(self, currency: str, *, remote: bool = True) -> None:
        currency = currency.upper()
        favourite_crypto_currency = (
            await FavouriteCryptoCurrency.objects().where(FavouriteCryptoCurrency.currency == currency).first()
        )
        if favourite_crypto_currency:
            if remote:
                await self._bit2me_remote_service.remove_favourite_crypto_currency(currency)
            await favourite_crypto_currency.delete()
            logger.info(f"Removed {currency} from favourite crypto currencies")

    async def get_non_favourite_crypto_currencies(self) -> list[str]:
        all_trading_crypto_currencies = await self._bit2me_remote_service.get_trading_crypto_currencies()
        favourite_crypto_currencies = await self.find_all()
        ret = sorted(
            [currency for currency in all_trading_crypto_currencies if currency not in favourite_crypto_currencies]
        )
        return ret
