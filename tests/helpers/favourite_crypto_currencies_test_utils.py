from faker import Faker

from crypto_trailing_stop.config.dependencies import get_application_container
from crypto_trailing_stop.infrastructure.services.favourite_crypto_currency_service import (
    FavouriteCryptoCurrencyService,
)
from tests.helpers.constants import MOCK_CRYPTO_CURRENCIES


async def prepare_favourite_crypto_currencies(
    faker: Faker, *, favourite_crypto_currencies: list[str] | None = None
) -> list[str]:
    favourite_crypto_currencies = favourite_crypto_currencies or faker.random_choices(
        MOCK_CRYPTO_CURRENCIES, length=faker.pyint(min_value=2, max_value=len(MOCK_CRYPTO_CURRENCIES) - 1)
    )
    favourite_crypto_currency_service: FavouriteCryptoCurrencyService = (
        get_application_container().infrastructure_container().services_container().favourite_crypto_currency_service()
    )
    for crypto_currency in favourite_crypto_currencies:
        await favourite_crypto_currency_service.add(crypto_currency)
    return favourite_crypto_currencies
