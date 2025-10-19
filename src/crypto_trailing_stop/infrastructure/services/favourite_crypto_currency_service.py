import logging
from typing import Any

from crypto_trailing_stop.infrastructure.adapters.remote.operating_exchange import AbstractOperatingExchangeService
from crypto_trailing_stop.infrastructure.database.models.favourite_crypto_currency import FavouriteCryptoCurrency

logger = logging.getLogger(__name__)


class FavouriteCryptoCurrencyService:
    def __init__(self, operating_exchange_service: AbstractOperatingExchangeService) -> None:
        self._operating_exchange_service = operating_exchange_service

    async def find_all(self) -> list[str]:
        favourite_crypto_currencies = await FavouriteCryptoCurrency.objects()
        ret = sorted(
            [favourite_crypto_currency.currency.upper() for favourite_crypto_currency in favourite_crypto_currencies]
        )
        return ret

    async def add(self, currency: str) -> None:
        currency = currency.upper()
        favourite_crypto_currency = (
            await FavouriteCryptoCurrency.objects().where(FavouriteCryptoCurrency.currency == currency).first()
        )
        if not favourite_crypto_currency:
            favourite_crypto_currency = FavouriteCryptoCurrency(currency=currency)
            await favourite_crypto_currency.save()
            logger.info(f"Added {currency} to favourite crypto currencies")

    async def remove(self, currency: str) -> None:
        currency = currency.upper()
        await FavouriteCryptoCurrency.delete().where(FavouriteCryptoCurrency.currency == currency)
        logger.info(f"Removed {currency} from favourite crypto currencies")

    async def get_non_favourite_crypto_currencies(self, *, client: Any | None = None) -> list[str]:
        all_trading_crypto_currencies = await self._operating_exchange_service.get_trading_crypto_currencies(
            client=client
        )
        favourite_crypto_currencies = await self.find_all()
        ret = sorted(
            [currency for currency in all_trading_crypto_currencies if currency not in favourite_crypto_currencies]
        )
        return ret
